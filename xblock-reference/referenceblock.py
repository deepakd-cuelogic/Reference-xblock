import pkg_resources
import requests

from urlparse import urlparse

from xblock.core import XBlock
from xblock.fields import Scope, Integer, String, List
from xblock.fragment import Fragment
from reference.models import ReferenceInfo
from xblockutils.resources import ResourceLoader

# use to load resources
loader = ResourceLoader(__name__)


class ReferenceInfoBlock(XBlock):
    """
    """

    ref_ids = List(
        help="URL of the video page at the provider",
        default=[],
        scope=Scope.settings)

    def student_view(self, context):
        """
        Create a fragment used to display the XBlock to a student.
        `context` is a dictionary used to configure the display (unused)

        Returns a `Fragment` object specifying the HTML, CSS, and JavaScript
        to display.
        """
        data = []
        if self.ref_ids:
            for id in self.ref_ids:
                # TO DO Use select in through ORM
                reference = ReferenceInfo.objects.get(id=id)
                data.append(reference)

        references = ReferenceInfo.objects.filter(id__in=ref_ids)
        print("Refernce by in query!!!", references)

        frag = Fragment()
        frag.add_content(
            loader.render_template('static/html/student_view.html',
                                   {'data': data, 'self': self}
            )
        )

        #Load Css
        frag.add_css(loader.load_unicode("static/css/referenceview.css"))

        #Load Js
        frag.add_javascript(loader.load_unicode('static/js/student.js'))
        frag.initialize_js('ReferenceInfoBlock')

        return frag

    def studio_view(self, context):
        """
        Create a fragment used to display the add view in the Studio.

        """
        references = ReferenceInfo.objects.all()
        data = []

        for i, dt in enumerate(references):
            ref_dict = {}
            ref_dict['ref_name'] = dt.ref_name
            ref_dict['ref_type'] = dt.ref_type
            ref_dict['ref_link'] = dt.ref_link
            ref_dict['ref_status'] = dt.ref_status
            ref_dict['ref_desc'] = dt.ref_desc
            ref_dict['id'] = dt.id
            data.append(ref_dict)


        frag = Fragment()
        frag.add_content(
            loader.render_template('static/html/staff_view.html',
                                   {'data': data, 'self': self})
        )
        #Load Js
        frag.add_javascript(loader.load_unicode('static/js/staff.js'))
        frag.initialize_js('ReferenceInfoBlock')

        return frag

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Called when submitting the form in Studio.
        """
        refrence_list = self.ref_ids

        ref_id = int(data.get('ref_id'))
        action = data.get('action')
        #event_type = data.pop('event_type')
        #print("event_type!!!", event_type)
        print("Action is ", action)

        if action == 'add':
            if ref_id in refrence_list:
                return {'status' : 304, 'message' : 'Record is  allready added.'}
            else:
                refrence_list.append(ref_id)
                response = {'status' : 200, 'message' : 'New record is Added.'}
        elif action == 'remove':
            if ref_id not in refrence_list:
                return {'status' : 404, 'message' : 'No record found to remove.'}
            else:
                refrence_list.remove(ref_id)
                response = {'status' : 200, 'message' : 'Remove successfully!!!.'}
        else:
            response = {'status' : 404, 'message' : 'Invalid Action!!!!!.'}
        # self.ref_list = repr(refrence_list)
        self.ref_ids = refrence_list

        #self.runtime.publish(self, self.ref_ids)

        return response
