// Dialog mode for the generated delete controls.
//
// One dialog for the whole page, built once and reused, so a list of two
// hundred rows does not ship two hundred copies of the same markup. The form
// carries its own question in data-confirm-delete; nothing here knows what a
// model is.
//
// An external file and no inline handler, because an interpreted attribute is
// invisible to a Content-Security-Policy and AI-UI's ui-Sprig validator
// refuses one whatever the admin grant says.
//
// With JavaScript off this file never runs and the form posts straight
// through. That is the trade dialog mode makes; page and inline modes do not
// make it.
(function () {
  "use strict";

  var dialog = null;
  var pending = null;

  function build() {
    dialog = document.createElement("dialog");
    var form = document.createElement("form");
    form.setAttribute("method", "dialog");

    var question = document.createElement("p");
    question.setAttribute("data-role", "question");
    form.appendChild(question);

    var cancel = document.createElement("button");
    cancel.setAttribute("value", "cancel");
    cancel.textContent = "Cancel";
    form.appendChild(cancel);

    var confirm = document.createElement("button");
    confirm.setAttribute("value", "confirm");
    confirm.textContent = "Delete";
    form.appendChild(confirm);

    dialog.appendChild(form);
    document.body.appendChild(dialog);

    dialog.addEventListener("close", function () {
      var form = pending;
      pending = null;
      if (form && dialog.returnValue === "confirm") {
        // submit() does not re-fire the submit event, so this cannot loop.
        form.submit();
      }
    });
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.hasAttribute || !form.hasAttribute("data-confirm-delete")) {
      return;
    }
    event.preventDefault();
    if (!dialog) {
      build();
    }
    dialog.querySelector("[data-role=question]").textContent =
      form.getAttribute("data-confirm-delete");
    pending = form;
    dialog.returnValue = "";
    dialog.showModal();
  });
})();
