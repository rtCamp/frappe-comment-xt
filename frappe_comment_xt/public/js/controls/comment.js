// eslint-disable-next-line
frappe.ui.form.ControlComment = class extends frappe.ui.form.ControlComment {
  make_wrapper() {
    this.comment_wrapper = !this.no_wrapper
      ? $(`
            <div class="comment-input-wrapper">
                <div class="comment-input-header">
                <span>${__("Comments")}</span>
                </div>
                <div class="comment-input-container">
                ${frappe.avatar(frappe.session.user, "avatar-medium")}
                    <div class="frappe-control col"></div>
                </div>
                <div class="comment-btn-container">
                    <div class="checkbox comment-visibility-input form-inline form-group">
                        <div class="comment-select-group">
                            <label for="status" class="visibility-label control-label text-muted small">
                                ${get_comment_visibility_icons("Visible to everyone")}
                            </label>
                            <div class="select-input form-control">
                                <select name="visibility" id="visibility" data-label="visibility" data-fieldtype="Select">
                                    <option value="Visible to everyone" selected="selected">
                                        Visible to everyone</option>
                                    <option value="Visible to mentioned">
                                        Visible to mentioned</option>
                                    <option value="Visible to only you">
                                        Visible to only you</option>
                                </select>
                                <div class="select-icon ">
                                    <svg class="icon  icon-sm">
                                        <use class="" href="#icon-select"></use>
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </div>
                    <button class="btn comment-submit-btn btn-comment btn-xs btn-primary disabled">
                        ${__("Add Comment")}
                    </button>
                </div>
            </div>
        `)
      : $('<div class="frappe-control"></div>');

    this.comment_wrapper.appendTo(this.parent);

    // wrapper should point to frappe-control
    this.$wrapper = !this.no_wrapper
      ? this.comment_wrapper.find(".frappe-control")
      : this.comment_wrapper;

    this.wrapper = this.$wrapper;

    this.button = this.comment_wrapper.find(".btn-comment");

    this.mention_wrapper = this.comment_wrapper.find(".checkbox");

    this.comment_visibility = this.comment_wrapper.find("#visibility");

    this.comment_visibility.on("change", () => {
      document.querySelector(".visibility-label").innerHTML =
        get_comment_visibility_icons(this.comment_visibility.prop("value"));
    });
  }

  submit() {
    this.on_submit &&
      this.on_submit(this.get_value(), this.comment_visibility.prop("value"));
  }

  update_state() {
    const value = this.get_value();
    if (strip_html(value).trim() != "" || value.includes("img")) {
      this.button.removeClass("disabled");
    } else {
      this.button.addClass("disabled");
    }
  }
};
