frappe.require(
  [
    "/assets/frappe_comment_xt/js/controls/replies.js",
    "/assets/frappe_comment_xt/js/controls/timeline.js",
    "/assets/frappe_comment_xt/js/controls/comment.js",
  ],
  () => {
    // Forms opened before these scripts loaded have already rendered their timelines undecorated
    Object.values(frappe.views.formview || {}).forEach((view) => {
      const frm = view.frm;
      if (frm?.footer && !frm.doc?.__islocal) update_comments_timeline(frm);
    });
  },
);
