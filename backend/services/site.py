import os
from core import db

DEFAULT_ANNOUNCEMENT = {
    "enabled": True,
    "title": "Hello, and welcome",
    "message": ("Thank you for visiting our website. It's new and has a lot of bugs, but if you use it "
                "and help us improve it, it's free forever. Thank you for your patience and support."),
    "signature": "— The Development team",
    "updated_at": "",
}


async def get_site_config():
    ann_doc = await db.settings.find_one({"key": "announcement"})
    ann = dict(DEFAULT_ANNOUNCEMENT)
    if ann_doc:
        ann.update(ann_doc.get("value", {}))
    sup = await db.settings.find_one({"key": "support_email"})
    support_email = ((sup or {}).get("value", {}) or {}).get("email", "") or os.environ.get("SUPPORT_EMAIL", "")
    return ann, support_email
