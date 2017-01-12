function CompletionBlock(runtime, element) {

    var $completion = $('.pb-completion-value', element);

    return {
        mode: null,
        mentoring: null,

        init: function(options) {
            this.mode = options.mode;
            this.mentoring = options.mentoring;
            $completion.on('change', options.onChange);
        },

        submit: function() {
            return $completion.is(':checked');
        },

        handleSubmit: function(result) {
            if (typeof result.submission !== 'undefined') {
                this.updateCompletion(result);
                $('.submit-result', element).css('visibility', 'visible');
            }
        },

        handleReview: function(result) {
            this.updateCompletion(result);
            $completion.prop('disabled', true);
        },

        clearResult: function() {
            $('.submit-result', element).css('visibility', 'hidden');
        },

        updateCompletion: function(result) {
            $completion.prop('checked', result.submission);
        }
    };

}
