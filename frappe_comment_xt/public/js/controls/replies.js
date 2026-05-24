// Maximum limit of nested threads allowed
const REPLY_LEVEL_LIMIT = 7;

function add_reply_button(time_line_item) {
  /* Add reply button to the parent comment */
  if ($(time_line_item).find(".custom-actions .reply-btn").length) {
    return;
  }
  const replyButton = $("<button>")
    .addClass("btn btn-xs btn-link reply-btn")
    .html('<i class="fa fa-reply"></i> Reply')
    .on("click", () => handle_reply(time_line_item));

  $(time_line_item).find(".custom-actions").append(replyButton);
}

function render_replies(
  commentSelector,
  commentId,
  allReplies,
  decrease_margin = false,
  comment_level = 1,
) {
  /*
   * Recursively render replies for a comment
   * allReplies: an object with commentId as key and an array of replies as value
   * decrease_margin: manually decrease the margin of the threaded reply container
   * comment_level: keep track of the depth of the comment
   */
  const replies = allReplies[commentId];
  if (!replies || Object.keys(replies).length === 0) {
    return;
  }

  const $comment = $(commentSelector);
  const $prevContainer = $comment.next(".threaded-reply-container");
  $prevContainer && $prevContainer.remove();

  const $replyContainer = $('<div class="threaded-reply-container"></div>');

  // Add vertical line
  $replyContainer.append('<div class="vertical-line"></div>');

  replies.forEach((reply) => {
    const $replyContent = $(`
            <div class="reply-wrapper">
                <div class="timeline-badge">
                    <svg class="icon icon-md">
                        <use href="#icon-small-message"></use>
                    </svg>
                </div>
                <div class="timeline-item frappe-card" data-doctype="Reply" data-level="${comment_level}" data-visibility="${
                  reply.custom_visibility
                }" id="comment-${reply.name}" data-name="${reply.name}">
                    <div class="timeline-content">
                        <div class="timeline-message-box">
                            <div>
                              <div>
                                <span class="text-muted">
                                    ${frappe.avatar(reply.comment_email, "avatar-medium")}
                                    <span class="timeline-user">${
                                      reply.comment_by ===
                                      frappe.session.user_fullname
                                        ? "You"
                                        : reply.comment_by
                                    } commented . </span>
                                    <span>&nbsp; ${frappe.datetime.comment_when(reply.creation)}</span>
                                </span>
                              ${update_the_comment_visibility(
                                frappe.session.user === "Administrator" ||
                                  reply.comment_email === frappe.session.user
                                  ? reply.custom_visibility
                                  : null,
                              )}
                              </div>
                            </div>
                            <hr />
                            <div class="read-mode">
                                <p>${reply.content}</p>
                            </div>
                            <div class="edit-mode"></div>
                       </div>
                    </div>
                </div>
            </div>
        `);

    if (decrease_margin) {
      $replyContainer.css("margin-left", "55px");
    }

    const $replyButton = $("<button>")
      .addClass("btn btn-xs btn-link reply-btn")
      .html('<i class="fa fa-reply"></i> Reply')
      .on("click", () => handle_reply("#comment-" + reply.name));

    $replyContainer.append($replyContent);

    const actionButtons = $("<div>").addClass("comment-actions");

    const moreButton = $("<a>")
      .addClass("action-btn")
      .attr({
        "data-toggle": "dropdown",
        "aria-haspopup": "true",
        "aria-expanded": "false",
      })
      .html(
        '<svg class="icon icon-sm"><use href="#icon-dot-horizontal"></use></svg>',
      );
    const dropdownMenu = $("<div>")
      .addClass("dropdown-menu small dropdown-menu-right")
      .append(
        $("<a>")
          .addClass("dropdown-item")
          .html("Copy Link")
          .on("click", () => handle_reply_copy("#comment-" + reply.name)),
      );

    // if owner or administrator, add the delete button
    if (
      frappe.model.can_delete("Comment") &&
      (frappe.session.user === "Administrator" ||
        reply.comment_email === frappe.session.user)
    ) {
      dropdownMenu.append(
        $("<a>")
          .addClass("dropdown-item")
          .html("Delete")
          .on("click", () => handle_reply_delete("#comment-" + reply.name)),
      );
    }

    const editButton = $("<button>")
      .addClass("btn btn-xs small")
      .html("Edit")
      .on("click", () =>
        handle_reply_edit(commentSelector, "#comment-" + reply.name),
      );

    moreButton.append(dropdownMenu);
    if (reply.comment_email === frappe.session.user) {
      actionButtons.append(editButton);
    }
    if (comment_level < REPLY_LEVEL_LIMIT) {
      actionButtons.append($replyButton);
    }
    actionButtons.append(moreButton);
    $replyContent.find(".text-muted").append(actionButtons);
  });

  $comment.after($replyContainer);

  replies.forEach((reply) => {
    render_replies(
      "#comment-" + reply.name,
      reply.name,
      allReplies,
      true,
      comment_level + 1,
    );
  });
}

function addThreadedReply(commentSelector, doctype, docname) {
  /*
   * Entry point to fetch and render replies for a comment
   * This will render the comment tree starting the given comment
   */
  const $comment = $(commentSelector);
  const commentId = $comment.data("name");
  const commentLevel = $comment.data("level") ?? 1;
  const isReply = $comment.data("doctype") === "Reply";

  frappe.call({
    method: "frappe_comment_xt.overrides.whitelist.comment.get_all_replies",
    args: {
      reference_name: docname,
      reference_doctype: doctype,
    },
    callback: (res) => {
      if (res.exc) {
        console.error(res.exc);
        return;
      }
      if (!res.message || !res.message[commentId].length) {
        // No replies found
        return;
      }

      render_replies(
        commentSelector,
        commentId,
        res.message,
        isReply,
        commentLevel + 1,
      );
    },
  });
}

function handle_reply(time_line_item) {
  /*
   * Handle the reply button click event
   */
  // if on Edit Mode, click on `Dismiss` button
  const parentDismiss = $(time_line_item).find(
    ".custom-actions.save-open > button:nth-child(2)",
  );
  if (parentDismiss.length) {
    parentDismiss.click();
  }
  const replyDismiss = $(time_line_item).find(".btn.cancel-edit");
  if (replyDismiss.length) {
    replyDismiss.click();
  }

  const $timeLineItem = $(time_line_item);
  const replyingToName = frappe.utils.escape_html(
    $timeLineItem.find(".avatar.avatar-medium").attr("title"),
  );
  if ($timeLineItem.find(".reply-container").length) {
    return;
  }

  const replyContainer = $(`
    <div class="reply-container">
      <div class="small text-muted mb-2">Replying to ${replyingToName}</div>
    </div>
`).appendTo($timeLineItem.find(".timeline-content"));

  const replyControl = frappe.ui.form.make_control({
    parent: replyContainer,
    df: {
      fieldtype: "Comment",
      fieldname: "comment",
      placeholder: __("Add a reply..."),
    },
    render_input: true,
    input_class: "edit-reply-input",
    enable_mentions: true,
    only_input: true,
    no_wrapper: true,
  });

  replyControl.refresh();

  const visibilitySelect = $(`
    <div class="checkbox comment-visibility-input form-inline form-group mt-3 ml-1 mb-2" >
      <div class="comment-select-group">
        <span class="text-muted small">Comment Visibility:</span>
        <label for="status" class="visibility-label control-label text-muted small">
          ${get_comment_visibility_icons("Visible to everyone")}
        </label>
        <div class="select-input form-control">
          <select name="visibility" id="visibility" data-label="visibility" data-fieldtype="Select">
            <option value="Visible to everyone" selected="selected">Visible to everyone</option>
            <option value="Visible to mentioned">Visible to mentioned</option>
            <option value="Visible to only you">Visible to only you</option>
          </select>
          <div class="select-icon">
            <svg class="icon icon-sm">
              <use class="" href="#icon-select"></use>
            </svg>
          </div>
        </div>
      </div>
    </div>
  `).appendTo(replyContainer);

  visibilitySelect.find("select").on("change", function () {
    const selectedValue = $(this).val();
    const newIcon = get_comment_visibility_icons(selectedValue);
    visibilitySelect.find(".visibility-label").html(newIcon);
  });

  const actionButtons = $(`
    <div class="reply-actions">
      <button class="btn btn-sm btn-primary submit-reply">${__("Comment")}</button>
      <button class="btn btn-sm btn-default cancel-reply">${__("Cancel")}</button>
    </div>
  `).appendTo(replyContainer);

  actionButtons.find(".submit-reply").on("click", () => {
    const replyContent = replyControl.get_value();
    const visibility = visibilitySelect.find("select").val();
    if (strip_html(replyContent).trim() != "" || replyContent.includes("img")) {
      submit_reply($timeLineItem, replyContent, visibility);
    }
  });

  actionButtons.find(".cancel-reply").on("click", () => {
    replyContainer.remove();
  });

  // Scroll to the reply container and focus on the input
  $("html, body").animate(
    {
      scrollTop: replyContainer.offset().top - $(window).height() / 2,
    },
    1000,
  );
  replyContainer.find(".ql-editor.ql-blank").focus();
}

function submit_reply(time_line_item, content, visibility) {
  /*
   * Submit the reply to the server and update the comments tree for the comment
   */
  frappe.call({
    method: "frappe.desk.form.utils.add_comment",
    args: {
      reference_doctype: this.cur_frm.doctype,
      reference_name: this.cur_frm.docname,
      custom_reply_to: $(time_line_item).data("name") || null,
      content: content,
      custom_visibility: visibility,
      comment_email: frappe.session.user,
      comment_by: frappe.session.user_fullname,
    },
    callback: (r) => {
      if (r.message) {
        $(time_line_item).find(".reply-container").remove();
        frappe.utils.play_sound("click");
        update_comments_timeline();
        addThreadedReply(
          time_line_item,
          this.cur_frm.doctype,
          this.cur_frm.docname,
        );
      }
    },
  });
}

function handle_reply_copy(commentSelector) {
  /*
   * Copy the comment URL to the clipboard
   */
  const $comment = $(commentSelector);
  const commentId = $comment.data("name");
  const currentUrl =
    frappe.urllib.get_base_url() +
    frappe.utils.get_form_link(this.cur_frm.doctype, this.cur_frm.docname);
  const commentUrl = `${currentUrl}#comment-${commentId}`;
  frappe.utils.copy_to_clipboard(commentUrl);
}

function handle_reply_delete(commentSelector) {
  /*
   * Delete the comment
   */
  const $comment = $(commentSelector);
  const commentId = $comment.data("name");

  frappe.confirm(__("Are you sure you want to delete this comment?"), () => {
    frappe.call({
      method: "frappe.client.delete",
      args: {
        doctype: "Comment",
        name: commentId,
      },
      callback: (r) => {
        if (r.exc) {
          frappe.msgprint(__("There was an error deleting the comment"));
        } else {
          frappe.show_alert({
            message: __("Comment deleted"),
            indicator: "green",
          });
        }
      },
    });
  });
}

function handle_reply_edit(parentComment, commentSelector) {
  /*
   * Edit the comment, prepare the edit mode and hide the read mode
   * Also handle the save and dismiss actions for the edit mode
   */
  const replyContainer = $(commentSelector).find(".reply-container");
  if (replyContainer) {
    replyContainer.remove();
  }
  const $comment = $(commentSelector);
  const $readMode = $comment.find(".read-mode");
  const $editMode = $comment.find(".edit-mode");
  const commentId = $comment.data("name");
  const doctype = this.cur_frm.doctype;
  const docname = this.cur_frm.docname;

  $readMode.hide();
  $editMode.show().empty();

  const editControl = frappe.ui.form.make_control({
    parent: $editMode,
    df: {
      fieldtype: "Comment",
      fieldname: "edit_comment",
      placeholder: __("Edit your reply..."),
    },
    render_input: true,
    enable_mentions: true,
    only_input: true,
    no_wrapper: true,
  });

  editControl.set_value($readMode.find(".ql-editor.read-mode").html());
  // make the background color white
  $editMode.find(".ql-editor").focus();
  editControl.refresh();

  const visibilitySelect = $(`
    <div class="checkbox comment-visibility-input form-inline form-group mt-3 ml-1 mb-2">
      <div class="comment-select-group">
        <span class="text-muted small">Comment Visibility:</span>
        <label for="status" class="visibility-label control-label text-muted small">
          ${get_comment_visibility_icons($comment.data("visibility") || "Visible to everyone")}
        </label>
        <div class="select-input form-control" >
          <select name="visibility" id="visibility" data-label="visibility" data-fieldtype="Select" >
            <option value="Visible to everyone" ${
              $comment.data("visibility") === "Visible to everyone"
                ? "selected"
                : ""
            }>Visible to everyone</option>
            <option value="Visible to mentioned" ${
              $comment.data("visibility") === "Visible to mentioned"
                ? "selected"
                : ""
            }>Visible to mentioned</option>
            <option value="Visible to only you" ${
              $comment.data("visibility") === "Visible to only you"
                ? "selected"
                : ""
            }>Visible to only you</option>
          </select>
          <div class="select-icon">
            <svg class="icon icon-sm">
              <use class="" href="#icon-select"></use>
            </svg>
          </div>
        </div>
      </div>
    </div>
  `).appendTo($editMode);

  visibilitySelect.find("select").on("change", function () {
    const selectedValue = $(this).val();
    const newIcon = get_comment_visibility_icons(selectedValue);
    visibilitySelect.find(".visibility-label").html(newIcon);
  });

  const $actionButtons = $(`
    <div class="reply-actions">
      <button class="btn btn-sm underline save-edit">${__("Save")}</button>
      <button class="btn btn-sm cancel-edit">${__("Dismiss")}</button>
    </div>
  `);
  if ($comment.find(".reply-actions").length === 0) {
    $actionButtons.prependTo($comment.find(".comment-actions"));
  }

  $actionButtons.find(".save-edit").on("click", function () {
    const newContent = editControl.get_value();
    frappe.call({
      method: "frappe.desk.form.utils.update_comment",
      args: {
        name: commentId,
        content: newContent,
        custom_visibility: visibilitySelect.find("select").val(),
      },
      callback: function (r) {
        if (!r.exc) {
          $comment.find(".comment-content").html(newContent);
          $editMode.hide();
          $readMode.show();

          addThreadedReply(parentComment, doctype, docname);
          frappe.show_alert({
            message: __("Comment updated"),
            indicator: "green",
          });
        } else {
          frappe.msgprint(__("There was an error updating the comment"));
        }
      },
    });
  });

  $actionButtons.find(".cancel-edit").on("click", function () {
    $editMode.hide();
    $readMode.show();
    $actionButtons.remove();
  });
}
