// NOTE: run `bench build` after making changes to this file
// alternatively, run `bench watch` to automatically build on file changes
// This is done this way in order to import and override the default Frappe FormTimeline class
import FormTimeline from "frappe/public/js/frappe/form/footer/form_timeline.js";

class CustomFormTimeline extends FormTimeline {
  get_comment_timeline_contents() {
    let comment_timeline_contents = [];
    (this.doc_info.comments || []).forEach((comment) => {
      // NOTE: The comment was being added on the timeline even if it was a reply on refresh
      // if the comment is a reply, don't add it to the timeline
      // truthy, not !== null: an unpatched response omits the field and must not blank the timeline
      if (comment.custom_reply_to) {
        return;
      }
      comment_timeline_contents.push(this.get_comment_timeline_item(comment));
    });
    return comment_timeline_contents;
  }

  render_timeline_items() {
    super.render_timeline_items();
    // frm.footer is unset during construction; Frappe's own render_complete -> footer.refresh()
    // re-renders once the form is up. The scripts load async, hence the optional call.
    if (this.frm.footer) window.update_comments_timeline?.(this.frm);
  }
}

frappe.ui.form.Footer = class extends frappe.ui.form.Footer {
  make_timeline() {
    this.frm.timeline = new CustomFormTimeline({
      parent: this.wrapper.find(".timeline"),
      frm: this.frm,
    });
  }

  make_comment_box() {
    this.frm.comment_box = frappe.ui.form.make_control({
      parent: this.wrapper.find(".comment-box"),
      render_input: true,
      only_input: true,
      enable_mentions: true,
      df: {
        fieldtype: "Comment",
        fieldname: "comment",
      },
      on_submit: (comment, custom_visibility) => {
        if (strip_html(comment).trim() != "" || comment.includes("img")) {
          this.frm.comment_box.disable();
          frappe
            .xcall("frappe.desk.form.utils.add_comment", {
              reference_doctype: this.frm.doctype,
              reference_name: this.frm.docname,
              content: comment,
              comment_email: frappe.session.user,
              comment_by: frappe.session.user_fullname,
              custom_visibility: custom_visibility,
            })
            .then((comment) => {
              let comment_item =
                this.frm.timeline.get_comment_timeline_item(comment);
              this.frm.comment_box.set_value("");
              frappe.utils.play_sound("click");
              this.frm.timeline.add_timeline_item(comment_item);
              this.frm.sidebar.refresh_comments_count &&
                this.frm.sidebar.refresh_comments_count();
            })
            .finally(() => {
              this.frm.comment_box.enable();
              window.update_comments_timeline?.(this.frm);
            });
          this.refresh();
        }
      },
    });
  }

  setup_replies() {
    // A public interface to the footer to render threaded replies
    const frm = this.frm;
    const docname = frm.docname;
    const doctype = frm.doctype;
    // Only this form's timeline: hidden pages of other doctypes keep their timelines in the DOM
    const $timelineItems = frm.timeline.timeline_items_wrapper;

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
        // No replies found
        if (!res.message || Object.keys(res.message).length === 0) return;

        $timelineItems
          .find('.timeline-item[data-doctype="Comment"]')
          .each(function () {
            const $item = $(this);
            const commentId = $item.data("name");
            render_replies($item, commentId, res.message, false, 1, frm);
          });
      },
    });
  }
};
