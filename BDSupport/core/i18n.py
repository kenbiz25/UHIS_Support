"""core/i18n.py

Bilingual (English / Bangla) copy for every hardcoded bot message - contact
intake, the first-touch menu, ticket confirmations, closing replies, etc.
The composer's own LLM-generated answers already respect `language` via
adapters.llm.openai_client.chat_complete_safe(language=...); this module
covers everything that ISN'T LLM-generated (menus, confirmations, prompts),
which previously stayed English-only regardless of the user's language.

Usage: t("key", language) where language is "en" or "bn" - unknown/blank
falls back to "en".
"""
from typing import List

STRINGS = {
    "en": {
        "lang_prompt": (
            "Please choose your language:\n"
            "1. English\n"
            "2. বাংলা (Bangla)"
        ),
        "contact_intake": (
            "Hi! Before we get started, could you share your name, email, and which "
            "division you're in? For example: \"Rahim Uddin, rahim@example.com, Dhaka\". "
            "No worries if you'd rather skip this - just reply 'skip'."
        ),
        "resolution_ack": "Wonderful, glad it's sorted now! I'm here anytime you need me again.",
        "closing_ack": "You're very welcome! Feel free to reach out anytime you need a hand.",
        "ticket_created": (
            "All set - I've logged this for our team.\n"
            "Ticket ID: {ref}\n"
            "Someone will follow up with you shortly."
        ),
        "ticket_failed": (
            "I tried to log this for our team but hit a snag on our end. "
            "Please reach out to support directly so we don't lose track of it."
        ),
        "ticket_declined": "No problem at all - I'm here if you change your mind or need anything else.",
        "handoff_ticket_offer": (
            "I want to make sure this gets properly looked at. "
            "Shall I log a support ticket so our team can follow up? "
            "Reply Yes to confirm, or No if you'd rather keep chatting with me."
        ),
        "handoff_open_ticket_note": "I've added this to your open ticket ({ref}) - our team will follow up.",
        "handoff_no_ticketing": "Please hold on - connecting you with a support teammate now.",
        "clarify_prompt": "Could you tell me a bit more - for example the exact error, where you got stuck, or your device type? That'll help me help you faster.",
        "menu_welcome": "Hi there! 👋 Welcome to SPICE Support. What can I help you with today?",
        "menu_items": [
            "1. Report a Problem\n   App not working, login trouble, sync issues",
            "2. Get Help Using SPICE\n   Registering patients, submitting reports, using features",
            "3. Check System Status\n   Downtime, known issues, maintenance updates",
            "4. Suggest an Improvement\n   Share an idea or request a new feature",
            "5. Training & Guides\n   Manuals, videos, getting-started help",
        ],
        "menu_reply_1": "Sorry to hear you're running into trouble! Could you describe what's happening - any error message, and the steps that led to it? A screenshot helps too, if you have one.",
        "menu_reply_2": (
            "Happy to help you get the most out of SPICE. A few common tasks:\n"
            "1. Register patients\n2. Submit reports\n3. Explore features\n\n"
            "Reply with a number, or just tell me what you're trying to do."
        ),
        "menu_reply_3_with_url": "Here's where to check current status and known issues: {url}",
        "menu_reply_3_no_url": "Let me know and I can check for any current known issues for you.",
        "menu_reply_4": "Love it - tell me more about the idea, including what problem it solves and who'd benefit. I'll pass it straight to our product team.",
        "menu_reply_5_with_url": "Here are our training materials: {url}",
        "menu_reply_5_no_url": "Happy to point you to training material - what topic are you looking for?",
        "menu_fallback": "Sorry, I didn't quite catch that - could you reply with a number from 1 to 5?",
    },
    "bn": {
        "lang_prompt": (
            "অনুগ্রহ করে আপনার ভাষা বেছে নিন:\n"
            "1. English\n"
            "2. বাংলা"
        ),
        "contact_intake": (
            "হ্যালো! শুরু করার আগে, আপনার নাম, ইমেইল এবং আপনি কোন বিভাগে আছেন তা জানাবেন কি? "
            "যেমন: \"রহিম উদ্দিন, rahim@example.com, ঢাকা\"। "
            "চাইলে এই ধাপ বাদ দিতে পারেন - শুধু 'skip' লিখুন।"
        ),
        "resolution_ack": "চমৎকার, এটা এখন ঠিক হয়ে গেছে জেনে ভালো লাগলো! আবার প্রয়োজন হলে যেকোনো সময় জানাবেন।",
        "closing_ack": "আপনাকে স্বাগতম! সাহায্যের প্রয়োজন হলে যেকোনো সময় যোগাযোগ করবেন।",
        "ticket_created": (
            "ঠিক আছে - এটি আমাদের টিমের জন্য লগ করা হয়েছে।\n"
            "টিকিট আইডি: {ref}\n"
            "শীঘ্রই কেউ আপনার সাথে যোগাযোগ করবে।"
        ),
        "ticket_failed": (
            "আমি এটি লগ করার চেষ্টা করেছিলাম কিন্তু আমাদের প্রান্তে একটি সমস্যা হয়েছে। "
            "অনুগ্রহ করে সরাসরি সাপোর্টের সাথে যোগাযোগ করুন।"
        ),
        "ticket_declined": "কোনো সমস্যা নেই - মত পরিবর্তন করলে বা অন্য কিছু প্রয়োজন হলে জানাবেন।",
        "handoff_ticket_offer": (
            "আমি নিশ্চিত করতে চাই এটি সঠিকভাবে দেখা হবে। "
            "আমাদের টিম যেন এটি অনুসরণ করতে পারে সেজন্য একটি সাপোর্ট টিকিট লগ করবো কি? "
            "নিশ্চিত করতে হ্যাঁ লিখুন, অথবা আমার সাথে কথা চালিয়ে যেতে চাইলে না লিখুন।"
        ),
        "handoff_open_ticket_note": "এটি আপনার খোলা টিকিটে ({ref}) যোগ করা হয়েছে - আমাদের টিম অনুসরণ করবে।",
        "handoff_no_ticketing": "একটু অপেক্ষা করুন - আপনাকে এখন একজন সাপোর্ট সহকর্মীর সাথে সংযুক্ত করা হচ্ছে।",
        "clarify_prompt": "আরেকটু বিস্তারিত বলবেন কি - যেমন সঠিক এরর মেসেজ, কোথায় আটকে গেছেন, বা আপনার ডিভাইসের ধরন? এতে আমি দ্রুত সাহায্য করতে পারবো।",
        "menu_welcome": "হ্যালো! 👋 SPICE সাপোর্টে স্বাগতম। আজ আপনাকে কীভাবে সাহায্য করতে পারি?",
        "menu_items": [
            "1. সমস্যা রিপোর্ট করুন\n   অ্যাপ কাজ করছে না, লগইন সমস্যা, সিঙ্ক সমস্যা",
            "2. SPICE ব্যবহারে সাহায্য নিন\n   রোগী নিবন্ধন, রিপোর্ট জমা, ফিচার ব্যবহার",
            "3. সিস্টেম স্ট্যাটাস দেখুন\n   ডাউনটাইম, পরিচিত সমস্যা, রক্ষণাবেক্ষণ তথ্য",
            "4. উন্নতির পরামর্শ দিন\n   একটি ধারণা শেয়ার করুন বা নতুন ফিচার অনুরোধ করুন",
            "5. প্রশিক্ষণ ও গাইড\n   ম্যানুয়াল, ভিডিও, শুরু করার সহায়তা",
        ],
        "menu_reply_1": "সমস্যার জন্য দুঃখিত! কী ঘটছে তা বলবেন কি - কোনো এরর মেসেজ থাকলে এবং কীভাবে এটি ঘটলো? সম্ভব হলে একটি স্ক্রিনশটও সাহায্য করবে।",
        "menu_reply_2": (
            "SPICE ব্যবহারে সাহায্য করতে পেরে খুশি। কিছু সাধারণ কাজ:\n"
            "1. রোগী নিবন্ধন\n2. রিপোর্ট জমা\n3. ফিচার দেখুন\n\n"
            "একটি নম্বর লিখুন, অথবা আপনি কী করতে চান তা বলুন।"
        ),
        "menu_reply_3_with_url": "বর্তমান স্ট্যাটাস এবং পরিচিত সমস্যা দেখতে এখানে যান: {url}",
        "menu_reply_3_no_url": "জানান, আমি আপনার জন্য বর্তমান পরিচিত সমস্যা পরীক্ষা করতে পারি।",
        "menu_reply_4": "চমৎকার - সমস্যাটি কী সমাধান করে এবং কে উপকৃত হবে সহ ধারণাটি সম্পর্কে আরও বলুন। আমি এটি সরাসরি আমাদের প্রোডাক্ট টিমের কাছে পাঠাবো।",
        "menu_reply_5_with_url": "আমাদের প্রশিক্ষণ উপকরণ এখানে: {url}",
        "menu_reply_5_no_url": "প্রশিক্ষণ উপকরণ দেখাতে পেরে খুশি হবো - কোন বিষয়ে খুঁজছেন?",
        "menu_fallback": "দুঃখিত, বুঝতে পারিনি - অনুগ্রহ করে ১ থেকে ৫ এর মধ্যে একটি সংখ্যা লিখুন।",
    },
}


def t(key: str, language: str = "en") -> str:
    lang = language if language in STRINGS else "en"
    return STRINGS[lang].get(key) or STRINGS["en"].get(key, "")


def menu_items(language: str = "en") -> List[str]:
    lang = language if language in STRINGS else "en"
    return STRINGS[lang].get("menu_items") or STRINGS["en"]["menu_items"]
