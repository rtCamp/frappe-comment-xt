frappe.require(["/assets/frappe_comment_xt/js/controls/replies.js"]);

/**Enable the HTML Editor field preview mode by default using the provided function */
const time_line_interval_loop = setInterval(() => {
  let html_time_line_item = document.querySelectorAll(".new-timeline > .timeline-items .timeline-item");

  if (html_time_line_item.length != 0) {
    update_comments_timeline();
  }
}, 300);

function get_comment_visibility_icons(visibility) {
  if (visibility == "Visible to everyone") {
    return `<i class="fa fa-globe visible-to-all"></i>
    `;
  }

  if (visibility == "Visible to mentioned") {
    return `<svg class="icon icon-md visible-to-mentioned">
        <use href="#icon-share"></use>
    </svg>`;
  }

  return `<svg class="icon icon-md visible-to-you">
        <use href="#icon-hide"></use>
    </svg>`;
}

function escapeHTML(str) {
  if (str == null) {
    return "";
  }
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function update_the_comment_visibility(visibility) {
  if (visibility) {
    const safeVisibility = escapeHTML(visibility);
    return `
            <span class="visibility-container" title="${safeVisibility}">
                <span class="visibility-info" data-visibility="${safeVisibility}">
                    ${get_comment_visibility_icons(visibility)}
                </span>
            </span>`;
  }

  return `<span class="visibility-container">
                <span class="visibility-info"></span>
            </span>`;
}

function add_visibility_icons(time_line_item, visibility) {
  if (time_line_item.querySelector(".visibility-container")) {
    time_line_item.querySelector(".visibility-container").remove();
  }

  time_line_item.querySelector(".timeline-message-box > span > span > span").innerHTML +=
    update_the_comment_visibility(visibility);
}

function update_comments_timeline() {
  // Select all the timeline comments and replies
  let html_time_line_items = document.querySelectorAll(".new-timeline > .timeline-items > .timeline-item");

  // Add the visibility icons to the comments
  for (let index = 0; index < html_time_line_items.length; index++) {
    // if the comment visibility are already added, skip
    if (html_time_line_items[index].querySelector(".visibility-info")) {
      break;
    }
    update_time_line(html_time_line_items[index]);
  }

  let replies_loaded = true;
  // Add the reply button to the comments
  for (let index = 0; index < html_time_line_items.length; index++) {
    // if the reply button is already added, skip
    if (html_time_line_items[index].querySelector(".reply-btn")) {
      break;
    }
    if (html_time_line_items[index].dataset.doctype == "Comment") {
      add_reply_button(html_time_line_items[index]);
      replies_loaded = false;
    }
  }

  if (!replies_loaded) {
    this.cur_frm.footer.setup_replies();
  }
}

function button_handle(event) {
  let html_time_line_items = document.querySelectorAll(".new-timeline > .timeline-items .timeline-item");

  for (let index = 0; index < html_time_line_items.length; index++) {
    if (html_time_line_items[index].dataset.name == event.target.dataset.name) {
      return button_override(html_time_line_items[index], event.target);
    }
  }
}

function update_time_line(time_line_item) {
  if (!("doctype" in time_line_item.dataset)) {
    return;
  }

  if (time_line_item.dataset.doctype != "Comment") {
    return;
  }

  frappe.call({
    method: "frappe_comment_xt.overrides.whitelist.comment.get_comment_visibility",
    args: {
      name: time_line_item.dataset.name,
    },
    callback: (res) => {
      add_visibility_icons(time_line_item, res?.message?.custom_visibility);
    },
  });

  let button = time_line_item.querySelector(".custom-actions button");

  if (!button) {
    return;
  }
  button.dataset.name = time_line_item.dataset.name;

  // Remove the event listener
  button.removeEventListener("click", button_handle, true);

  // Add the event listener
  button.addEventListener("click", button_handle, true);

  time_line_item.querySelector(".custom-actions").lastChild.addEventListener("click", () => {
    time_line_item.querySelector(".timeline-comment").remove();
    time_line_item.querySelector(".custom-actions").classList.remove("save-open");
  });
}

function button_override(time_line_item, button) {
  if (time_line_item.querySelector(".custom-actions").classList.contains("save-open")) {
    handle_save(time_line_item, button);
  } else {
    handle_edit(time_line_item, button);
  }
}

function handle_save(time_line_item, button) {
  frappe.call({
    method: "frappe.desk.form.utils.update_comment",
    args: {
      name: time_line_item.dataset.name,
      content: time_line_item.querySelector(".comment-edit-box .ql-editor").innerHTML,
      custom_visibility: time_line_item.querySelector("#visibility").value,
    },
    callback: () => {
      time_line_item.querySelector(".timeline-comment").remove();
      time_line_item.querySelector(".custom-actions").classList.remove("save-open");
      update_time_line(time_line_item);
    },
  });
}

function handle_edit(time_line_item, button) {
  const replyContainer = time_line_item.querySelector(".reply-container");
  if (replyContainer) {
    replyContainer.remove();
  }
  time_line_item.querySelector(".timeline-message-box").append(get_input_html(time_line_item));
  time_line_item.querySelector("#visibility").value =
    time_line_item.querySelector(".visibility-info").dataset.visibility;
  time_line_item.querySelector(".custom-actions").classList.add("save-open");
}

function get_input_html(time_line_item) {
  const div = document.createElement("div");
  div.className = "checkbox timeline-comment form-inline form-group";
  div.innerHTML = `
        <div class="comment-select-group">
            <label for="status" class="control-label text-muted small">Comment visibility:</label>
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
    `;

  div.querySelector("#visibility").addEventListener("change", (event) => {
    add_visibility_icons(time_line_item, event.target.value);
  });

  return div;
}
