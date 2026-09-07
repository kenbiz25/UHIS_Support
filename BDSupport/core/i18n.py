"""core/i18n.py

Bilingual (English / Bangla) copy for every hardcoded bot message - contact
intake, the first-touch menu, structured-intake field prompts, ticket
confirmations, closing replies, etc. The composer's own LLM-generated
answers already respect `language` via
adapters.llm.openai_client.chat_complete_safe(language=...); this module
covers everything that ISN'T LLM-generated (menus, confirmations, prompts),
which previously stayed English-only regardless of the user's language.

Usage: t("key", language) where language is "en" or "bn" - unknown/blank
falls back to "en".
"""
from typing import List

STRINGS = {
    "en": {
        # Single combined first-touch ask: language choice + optional
        # contact details in one round trip instead of two sequential
        # prompts. Bilingual by design since language isn't known yet.
        "first_touch_intake": (
            "Hi! 👋 Welcome to SPICE Support.\n\n"
            "Please choose your language / আপনার ভাষা বেছে নিন:\n"
            "1. English\n"
            "2. বাংলা (Bangla)\n\n"
            "And if you'd like, share your name, email, and division too - e.g. "
            "\"1, Rahim Uddin, rahim@example.com, Dhaka\". Or just reply with the "
            "language number - you can skip the rest."
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

        # --- First-touch menu ---
        "menu_welcome": "Hi there! 👋 Welcome to SPICE Support. What can I help you with today?",
        "menu_items": [
            "1. Account & Access\n   Locked/disabled account, forgot password, can't log in",
            "2. Add/Update SK, SS, CC or Location Info\n   New or changed health worker, clinic, or union/village mapping",
            "3. Dashboard & Reports\n   QuickSight access, incentive/NCD/glass-sold reports",
            "4. App Problem\n   Crash, QR code, sync, or other app bugs",
            "5. Get Help Using SPICE\n   Registering patients, submitting reports, using features",
            "6. Training & Guides\n   Manuals, videos, getting-started help",
            "7. Something else\n   Talk to a person about anything not listed above",
        ],
        "menu_fallback": "Sorry, I didn't quite catch that - could you reply with a number from 1 to 7?",

        # Categories 5 (Get Help) and 6 (Training) keep their old-style
        # canned/dynamic replies - they're genuinely "how do I..." questions
        # a knowledge base or a doc link can answer, unlike 1-4 and 7 which
        # go through structured intake straight to a ticket (see below).
        "menu_reply_help": (
            "Happy to help you get the most out of SPICE. A few common tasks:\n"
            "1. Register patients\n2. Submit reports\n3. Explore features\n\n"
            "Reply with a number, or just tell me what you're trying to do."
        ),
        "menu_reply_training_with_url": "Here are our training materials: {url}",
        "menu_reply_training_no_url": "Happy to point you to training material - what topic are you looking for?",

        # --- Structured intake: per-category field prompts ---
        # Category 1: Account & Access
        "intake_1_account_id": "What's the phone number, mHealth number, or SPICE ID for the affected account?",
        "intake_1_problem": "What's happening - e.g. locked/disabled, forgot password, can't log in? Please describe briefly.",
        # Category 2: Add/Update SK, SS, CC or Location Info
        "intake_2_location": "Which District/Upazila/Union is this for?",
        "intake_2_change_details": "What needs to be added or changed? (e.g. SK/SS/CC name, and the new info)",
        "intake_2_mhealth_number": "If you have it, what's the mHealth number for this? (reply 'skip' if you don't have one)",
        # Category 3: Dashboard & Reports
        "intake_3_request": "What do you need - QuickSight login access, or a specific report? If a report, please say which one and the date range.",
        "intake_3_contact_email": "Which email (or phone number) should we use for this?",
        # Category 4: App Problem
        "intake_4_problem": "Please describe what's happening, including any error message you saw.",
        "intake_4_feature": "Which screen or feature is this on? (e.g. login, QR scan, patient entry, sync, report submission)",
        "intake_4_device_info": "What phone/tablet model and app version are you using, if you know it? (reply 'skip' if unsure)",
        # Category 7: Something else
        "intake_7_problem": "Please describe what you need help with, and I'll create a ticket for our team.",

        "intake_skip_words": "skip,none,na,n/a,no",
    },
    "bn": {
        "first_touch_intake": (
            "হ্যালো! 👋 SPICE সাপোর্টে স্বাগতম।\n\n"
            "অনুগ্রহ করে আপনার ভাষা বেছে নিন / Please choose your language:\n"
            "1. English\n"
            "2. বাংলা (Bangla)\n\n"
            "চাইলে আপনার নাম, ইমেইল এবং বিভাগও জানাতে পারেন - যেমন "
            "\"1, রহিম উদ্দিন, rahim@example.com, ঢাকা\"। অথবা শুধু ভাষার নম্বরটি লিখুন - বাকিটা বাদ দিতে পারেন।"
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
            "1. অ্যাকাউন্ট ও অ্যাক্সেস\n   লকড/নিষ্ক্রিয় অ্যাকাউন্ট, পাসওয়ার্ড ভুলে যাওয়া, লগইন করতে না পারা",
            "2. SK, SS, CC বা লোকেশন তথ্য যোগ/আপডেট\n   নতুন বা পরিবর্তিত স্বাস্থ্যকর্মী, ক্লিনিক, বা ইউনিয়ন/গ্রাম ম্যাপিং",
            "3. ড্যাশবোর্ড ও রিপোর্ট\n   QuickSight অ্যাক্সেস, ইনসেনটিভ/NCD/গ্লাস বিক্রির রিপোর্ট",
            "4. অ্যাপ সমস্যা\n   ক্র্যাশ, QR কোড, সিঙ্ক, বা অন্যান্য অ্যাপ বাগ",
            "5. SPICE ব্যবহারে সাহায্য নিন\n   রোগী নিবন্ধন, রিপোর্ট জমা, ফিচার ব্যবহার",
            "6. প্রশিক্ষণ ও গাইড\n   ম্যানুয়াল, ভিডিও, শুরু করার সহায়তা",
            "7. অন্য কিছু\n   উপরে তালিকাভুক্ত নয় এমন কিছু নিয়ে একজন মানুষের সাথে কথা বলুন",
        ],
        "menu_fallback": "দুঃখিত, বুঝতে পারিনি - অনুগ্রহ করে ১ থেকে ৭ এর মধ্যে একটি সংখ্যা লিখুন।",

        "menu_reply_help": (
            "SPICE ব্যবহারে সাহায্য করতে পেরে খুশি। কিছু সাধারণ কাজ:\n"
            "1. রোগী নিবন্ধন\n2. রিপোর্ট জমা\n3. ফিচার দেখুন\n\n"
            "একটি নম্বর লিখুন, অথবা আপনি কী করতে চান তা বলুন।"
        ),
        "menu_reply_training_with_url": "আমাদের প্রশিক্ষণ উপকরণ এখানে: {url}",
        "menu_reply_training_no_url": "প্রশিক্ষণ উপকরণ দেখাতে পেরে খুশি হবো - কোন বিষয়ে খুঁজছেন?",

        "intake_1_account_id": "প্রভাবিত অ্যাকাউন্টের ফোন নম্বর, mHealth নম্বর, বা SPICE ID কী?",
        "intake_1_problem": "কী ঘটছে - যেমন লকড/নিষ্ক্রিয়, পাসওয়ার্ড ভুলে গেছেন, লগইন করতে পারছেন না? সংক্ষেপে বলুন।",
        "intake_2_location": "এটি কোন জেলা/উপজেলা/ইউনিয়নের জন্য?",
        "intake_2_change_details": "কী যোগ বা পরিবর্তন করতে হবে? (যেমন SK/SS/CC নাম, এবং নতুন তথ্য)",
        "intake_2_mhealth_number": "থাকলে, এর mHealth নম্বরটি কী? (না থাকলে 'skip' লিখুন)",
        "intake_3_request": "আপনার কী দরকার - QuickSight লগইন অ্যাক্সেস, নাকি একটি নির্দিষ্ট রিপোর্ট? রিপোর্ট হলে, কোনটি এবং কোন তারিখের পরিসীমা জানান।",
        "intake_3_contact_email": "এর জন্য কোন ইমেইল (বা ফোন নম্বর) ব্যবহার করবো?",
        "intake_4_problem": "কী ঘটছে তা বিস্তারিত বলুন, কোনো এরর মেসেজ থাকলে সেটাও।",
        "intake_4_feature": "এটি কোন স্ক্রিন বা ফিচারে হচ্ছে? (যেমন লগইন, QR স্ক্যান, রোগী তথ্য প্রবেশ, সিঙ্ক, রিপোর্ট জমা)",
        "intake_4_device_info": "আপনি কোন ফোন/ট্যাবলেট মডেল এবং অ্যাপ ভার্সন ব্যবহার করছেন, জানা থাকলে বলুন। (না জানলে 'skip' লিখুন)",
        "intake_7_problem": "আপনার কী সাহায্য দরকার তা বলুন, আমি আমাদের টিমের জন্য একটি টিকিট তৈরি করবো।",

        "intake_skip_words": "skip,স্কিপ,না,none,na,n/a,no",
    },
}


def t(key: str, language: str = "en") -> str:
    lang = language if language in STRINGS else "en"
    return STRINGS[lang].get(key) or STRINGS["en"].get(key, "")


def menu_items(language: str = "en") -> List[str]:
    lang = language if language in STRINGS else "en"
    return STRINGS[lang].get("menu_items") or STRINGS["en"]["menu_items"]
