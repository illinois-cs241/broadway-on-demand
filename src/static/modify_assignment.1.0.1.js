/**
 * Depends on jquery.validate plugin and moment.js
 * Validates form that edits or add assignments. Then submit it to given endpoint.
 * Also displays error, spin save icon when loading.
 * @param formName Name of form to validate
 * @param postUrl The url to send form data to
 * @param errorSelector Selector for element to display error
 * @param saveBtn Selector for save button
 * @param saveBtnIcon The selector for icon on save button
 * @param modalSelector The selector for form modal
 */
function modifyAssignment(formName, postUrl, errorSelector, saveBtn, saveBtnIcon, modalSelector) {
    // custom validators
    $.validator.addMethod("check_id", function(value, element) {
        return this.optional(element) || /^[a-zA-Z0-9_\-]+$/.test(value);
    }, "ID must only contain: a-z A-Z 0-9 _ -");

    $.validator.addMethod("check_datetime", function(value, element) {
        return this.optional(element) || moment(value).isValid();
    }, "Please provide valid datetime, e.g. 2013-02-08 19:30")

    // form validation
    $(`form[name="${formName}"]`).validate({
        errorClass: "text-danger",
        errorElement: "small",
        rules: {
            aid: {
                required: true,
                check_id: true,
            },
            max_runs: "required",
            quota: "required",
            start: {
                required: true,
                check_datetime: true,
            },
            end: {
                required: true,
                check_datetime: true,
            },
            visibility: "required",
            config: "required",
        },
        errorPlacement: function(error, element) {
            if (element.attr("type") == "radio") {
                // radio are grouped by divs, so insert at the end of one level above
                let parent = element.parent().parent();
                parent.append("<br/>");
                parent.append(error);
            } else {
                // normally insert right after input element
                error.insertAfter(element);
            }
        },
        submitHandler: function(form, event) {
            event.preventDefault();
            // raw data has the form: [{name: "name of input field", value: "input value"}, ...]
            let rawData = $(form).serializeArray();
            let formData = {};
            for (let i = 0; i < rawData.length; i++) {
                let fieldName = rawData[i].name;
                let fieldVal = rawData[i].value;
                // Convert date string to special format
                if (fieldName == "start" || fieldName == "end") {
                    fieldVal = moment(fieldVal).format("YYYY-MM-DDTHH:mm");
                }
                formData[fieldName] = fieldVal;
            }
            $.ajax({
                type: "POST",
                url: postUrl,
                data: formData,
                beforeSend: function () {
                    $(errorSelector).html('').fadeOut();
                    $(saveBtnIcon).addClass("fa-spin");
                    $(saveBtn).prop('disabled', true);
                },
                success: function () {
                    $(modalSelector).modal('hide');
                    location.reload();
                },
                error: function (xhr) {
                    if (!xhr.responseText) {
                        $(errorSelector).html("Save failed. Please try again.").fadeIn();
                    } else {
                        $(errorSelector).html(xhr.responseText).fadeIn();
                    }
                }
            }).always(() => {
                $(saveBtnIcon).removeClass("fa-spin");
                $(saveBtn).prop('disabled', false);
            });
        }
    });
}