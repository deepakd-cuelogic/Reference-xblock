# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2015 Harvard, edX & OpenCraft
#
# This software's license gives you freedom; you can copy, convey,
# propagate, redistribute and/or modify this program under the terms of
# the GNU Affero General Public License (AGPL) as published by the Free
# Software Foundation (FSF), either version 3 of the License, or (at your
# option) any later version of the AGPL published by the FSF.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero
# General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program in a file in the toplevel directory called
# "AGPLv3".  If not, see <http://www.gnu.org/licenses/>.
#

# Imports ###########################################################

import logging
from lazy import lazy

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils.crypto import get_random_string

from .models import Answer

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String
from xblock.fragment import Fragment
from xblock.validation import ValidationMessage
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin, XBlockWithPreviewMixin
from problem_builder.sub_api import SubmittingXBlockMixin, sub_api
from .mixins import QuestionMixin, XBlockWithTranslationServiceMixin
import uuid


# Globals ###########################################################

log = logging.getLogger(__name__)
loader = ResourceLoader(__name__)


# Make '_' a no-op so we can scrape strings
def _(text):
    return text

# Classes ###########################################################


class AnswerMixin(XBlockWithPreviewMixin, XBlockWithTranslationServiceMixin):
    """
    Mixin to give an XBlock the ability to read/write data to the Answers DB table.
    """
    def _get_course_id(self):
        """ Get a course ID if available """
        return getattr(self.runtime, 'course_id', 'all')

    def _get_student_id(self):
        """ Get student anonymous ID or normal ID """
        try:
            return self.runtime.anonymous_student_id
        except AttributeError:
            return self.scope_ids.user_id

    @staticmethod
    def _fetch_model_object(name, student_id, course_id):
        answer = Answer.objects.get(
            Q(name=name),
            Q(student_id=student_id),
            Q(course_key=course_id) | Q(course_id=course_id)
        )
        if not answer.course_key:
            answer.course_key = answer.course_id
        return answer

    @staticmethod
    def _create_model_object(name, student_id, course_id):
        # Try to store the course_id into the deprecated course_id field if it fits into
        # the 50 character limit for compatibility with old code. If it does not fit,
        # use a random temporary value until the column gets removed in next release.
        # This should not create any issues with old code running alongside the new code,
        # since Answer blocks don't work with old code when course_id is longer than 50 chars anyway.
        if len(course_id) > 50:
            # The deprecated course_id field cannot be blank. It also needs to be unique together with
            # the name and student_id fields, so we cannot use a static placeholder value, we generate
            # a random value instead, to make the database happy.
            deprecated_course_id = get_random_string(24)
        else:
            deprecated_course_id = course_id
        answer = Answer(student_id=student_id, name=name, course_key=course_id, course_id=deprecated_course_id)
        answer.save()
        return answer

    def get_model_object(self, name=None):
        """
        Fetches the Answer model object for the answer named `name`
        """
        # By default, get the model object for the current answer's name
        if not name:
            name = self.name
        # Consistency check - we should have a name by now
        if not name:
            raise ValueError('AnswerBlock.name field need to be set to a non-null/empty value')

        student_id = self._get_student_id()
        course_id = self._get_course_id()

        try:
            answer_data = self._fetch_model_object(name, student_id, course_id)
        except Answer.DoesNotExist:
            try:
                # Answer object does not exist, try to create it.
                answer_data = self._create_model_object(name, student_id, course_id)
            except (IntegrityError, ValidationError):
                # Integrity/validation error means the object must have been created in the meantime,
                # so fetch the new object from the db.
                answer_data = self._fetch_model_object(name, student_id, course_id)

        return answer_data

    @property
    def student_input(self):
        if self.name:
            return self.get_model_object().student_input
        return ''

    @XBlock.json_handler
    def answer_value(self, data, suffix=''):
        """ Current value of the answer, for refresh by client """
        return {'value': self.student_input}

    @XBlock.json_handler
    def refresh_html(self, data, suffix=''):
        """ Complete HTML view of the XBlock, for refresh by client """
        frag = self.mentoring_view({})
        return {'html': frag.content}

    def validate_field_data(self, validation, data):
        """
        Validate this block's field data.
        """
        super(AnswerMixin, self).validate_field_data(validation, data)

        def add_error(msg):
            validation.add(ValidationMessage(ValidationMessage.ERROR, msg))

        if not data.name:
            add_error(u"A Question ID is required.")


@XBlock.needs("i18n")
class AnswerBlock(SubmittingXBlockMixin, AnswerMixin, QuestionMixin, StudioEditableXBlockMixin, XBlock):
    """
    A field where the student enters an answer

    Must be included as a child of a mentoring block. Answers are persisted as django model instances
    to make them searchable and referenceable across xblocks.
    """
    CATEGORY = 'pb-answer'
    STUDIO_LABEL = _(u"Long Answer")
    answerable = True

    name = String(
        display_name=_("Question ID (name)"),
        help=_("The ID of this block. Should be unique unless you want the answer to be used in multiple places."),
        default="",
        scope=Scope.content
    )
    default_from = String(
        display_name=_("Default From"),
        help=_("If a question ID is specified, get the default value from this answer."),
        default=None,
        scope=Scope.content
    )
    min_characters = Integer(
        display_name=_("Min. Allowed Characters"),
        help=_("Minimum number of characters allowed for the answer"),
        default=0,
        scope=Scope.content
    )
    question = String(
        display_name=_("Question"),
        help=_("Question to ask the student"),
        scope=Scope.content,
        default="",
        multiline_editor=True,
    )

    editable_fields = ('question', 'name', 'min_characters', 'weight', 'default_from', 'display_name', 'show_title')

    @lazy
    def student_input(self):
        """
        The student input value, or a default which may come from another block.
        Read from a Django model, since XBlock API doesn't yet support course-scoped
        fields or generating instructor reports across many student responses.
        """
        # Only attempt to locate a model object for this block when the answer has a name
        if not self.name:
            return ''

        student_input = self.get_model_object().student_input

        # Default value can be set from another answer's current value
        if not student_input and self.default_from:
            student_input = self.get_model_object(name=self.default_from).student_input

        return student_input

    def mentoring_view(self, context=None):
        """ Render this XBlock within a mentoring block. """
        context = context.copy() if context else {}
        context['self'] = self
        context['hide_header'] = context.get('hide_header', False) or not self.show_title
        html = loader.render_template('templates/html/answer_editable.html', context)

        fragment = Fragment(html)
        fragment.add_css_url(self.runtime.local_resource_url(self, 'public/css/answer.css'))
        fragment.add_javascript_url(self.runtime.local_resource_url(self, 'public/js/answer.js'))
        fragment.initialize_js('AnswerBlock')
        return fragment

    def student_view(self, context=None):
        """ Normal view of this XBlock, identical to mentoring_view """
        return self.mentoring_view(context)

    def get_results(self, previous_response=None):
        # Previous result is actually stored in database table-- ignore.
        return {
            'student_input': self.student_input,
            'status': self.status,
            'weight': self.weight,
            'score': 1 if self.status == 'correct' else 0,
        }

    def get_last_result(self):
        return self.get_results(None) if self.student_input else {}

    def submit(self, submission):
        """
        The parent block is handling a student submission, including a new answer for this
        block. Update accordingly.
        """
        self.student_input = submission[0]['value'].strip()
        self.save()

        if sub_api:
            # Also send to the submissions API:
            item_key = self.student_item_key
            # Need to do this by our own ID, since an answer can be referred to multiple times.
            item_key['item_id'] = self.name
            sub_api.create_submission(item_key, self.student_input)

        log.info(u'Answer submitted for`{}`: "{}"'.format(self.name, self.student_input))
        return self.get_results()

    @property
    def status(self):
        answer_length_ok = self.student_input
        if self.min_characters > 0:
            answer_length_ok = len(self.student_input.strip()) >= self.min_characters

        return 'correct' if answer_length_ok else 'incorrect'

    @property
    def completed(self):
        return self.status == 'correct'

    def save(self):
        """
        Replicate data changes on the related Django model used for sharing of data accross XBlocks
        """
        super(AnswerBlock, self).save()

        student_id = self._get_student_id()
        if not student_id:
            return  # save() gets called from the workbench homepage sometimes when there is no student ID

        # Only attempt to locate a model object for this block when the answer has a name
        if self.name:
            answer_data = self.get_model_object()
            if answer_data.student_input != self.student_input:
                answer_data.student_input = self.student_input
                answer_data.save()

    @classmethod
    def get_template(cls, template_id):
        """
        Used to interact with Studio's create_xblock method to instantiate pre-defined templates.
        """
        # Generate a random 'name' value
        if template_id == 'studio_default':
            return {'data': {'name': uuid.uuid4().hex[:7]}}
        return {'metadata': {}, 'data': {}}

    def student_view_data(self):
        """
        Returns a JSON representation of the student_view of this XBlock,
        retrievable from the Course Block API.
        """
        return {'question': self.question}


@XBlock.needs("i18n")
class AnswerRecapBlock(AnswerMixin, StudioEditableXBlockMixin, XBlock):
    """
    A block that displays an answer previously entered by the student (read-only).
    """
    CATEGORY = 'pb-answer-recap'
    STUDIO_LABEL = _(u"Long Answer Recap")

    name = String(
        display_name=_("Question ID"),
        help=_("The ID of the question for which to display the student's answer."),
        scope=Scope.content,
    )
    display_name = String(
        display_name=_("Title"),
        help=_("Title of this answer recap section"),
        scope=Scope.content,
        default="",
    )
    description = String(
        display_name=_("Description"),
        help=_("Description of this answer (optional). Can include HTML."),
        scope=Scope.content,
        default="",
    )
    editable_fields = ('name', 'display_name', 'description')

    css_path = 'public/css/answer.css'

    def mentoring_view(self, context=None):
        """ Render this XBlock within a mentoring block. """
        context = context.copy() if context else {}
        student_submissions_key = context.get('student_submissions_key')
        context['title'] = self.display_name
        context['description'] = self.description
        if student_submissions_key:
            location = self.location.replace(branch=None, version=None)  # Standardize the key in case it isn't already
            target_key = {
                'student_id': student_submissions_key,
                'course_id': unicode(location.course_key),
                'item_id': self.name,
                'item_type': u'pb-answer',
            }
            submissions = sub_api.get_submissions(target_key, limit=1)
            try:
                context['student_input'] = submissions[0]['answer']
            except IndexError:
                context['student_input'] = None
        else:
            context['student_input'] = self.student_input
        html = loader.render_template('templates/html/answer_read_only.html', context)

        fragment = Fragment(html)
        fragment.add_css_url(self.runtime.local_resource_url(self, self.css_path))
        fragment.add_javascript_url(self.runtime.local_resource_url(self, 'public/js/answer_recap.js'))
        fragment.initialize_js('AnswerRecapBlock')
        return fragment

    def student_view(self, context=None):
        """ Normal view of this XBlock, identical to mentoring_view """
        return self.mentoring_view(context)