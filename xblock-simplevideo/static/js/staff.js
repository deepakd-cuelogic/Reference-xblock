function ReferenceInfoBlock(runtime, element) {
    $(element).find('.save-button').bind('click', function(e) {
	e.preventDefault();
	var handlerUrl = runtime.handlerUrl(element, 'studio_submit');
	var data = {
	    ref_id :$(this).data('refid'),
	    action :'add'
	};
	$.post(handlerUrl, JSON.stringify(data)).done(function(response) {
	    if(response.status==='success'){
		location.reload();
	    }
	    runtime.notify('save', {state: 'saved'});
	    console.log("response:")
	});
    });

    $(element).find('.remove-button').bind('click', function(e) {
	e.preventDefault();
	var handlerUrl = runtime.handlerUrl(element, 'studio_submit');
	var data = {
	    ref_id :$(this).data('refid'),
	    action :'remove'
	};
	$.post(handlerUrl, JSON.stringify(data)).done(function(response) {
	    if(response.status==='success'){
		location.reload();
	    }
	    console.log(response)
	    runtime.notify('remove', {state: 'removed'});
	});
    });


    $(element).find('.cancel-button').bind('click', function() {
	runtime.notify('cancel', {});
    });
}
