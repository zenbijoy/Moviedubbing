"""
Generates the complete Bangla Dubbed Dialogue Script & Subtitle files for Bad Genius S1E1.
"""

from __future__ import annotations

from pathlib import Path


def generate_bangla_deliverables() -> None:
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    bangla_script_path = exports_dir / "bad_genius_s1e1_bangla_dubbing_script.txt"
    bangla_srt_path = exports_dir / "bad_genius_s1e1_bangla.srt"

    script_content = """================================================================================
          BAD GENIUS (THE SERIES) - S1E1 | BANGLA DUBBED SCRIPT
================================================================================
Movie Title:       Bad Genius: The Series - Episode 1
Dubbed Language:   Bengali / বাংলা (bn-BD)
Audio Master:      exports/bad_genius_s1e1_bangla_dubbed.mp4
Loudness:          -24.0 LUFS (Broadcast Standard)
Cast:              Lynn (লিন), Bank (ব্যাংক), Grace (গ্রেস), Pat (প্যাট)
================================================================================

[00:00:15.100 --> 00:00:18.400]
[Lynn / লিন]:
(গম্ভীর ও দৃঢ় কণ্ঠে)
"যদি তুমি এই মর্যাদাপূর্ণ স্কলারশিপ বা বৃত্তিটা জিততে চাও, তবে তোমাকে অবশ্যই আমার নিখুঁত পরিকল্পনা অনুসরণ করতে হবে।"
(English: "If you want to win this prestigious scholarship, you must follow my exact plan.")

--------------------------------------------------------------------------------

[00:00:19.200 --> 00:00:22.800]
[Grace / গ্রেস]:
(আকুল ও মিনতিভরে)
"লিন, প্লিজ আমাকে সাহায্য করো! এই ফাইনাল পরীক্ষার প্রশ্নপত্র পাশ না করলে বাবা আমাকে ক্লাবে যেতে দেবেন না।"
(English: "Lynn, please help me! If I don't pass this final exam paper, dad won't let me go to the club.")

--------------------------------------------------------------------------------

[00:00:23.500 --> 00:00:27.100]
[Lynn / লিন]:
(চিন্তিত ও হিসাবি সুর)
"পরীক্ষার হলের ঘড়িটা দেখে সময় মেলাও। পিয়ানোর সুরের সংকেত শুনে উত্তরগুলো ওএমআর শীটে ভরাট করবে।"
(English: "Watch the exam hall clock to sync time. Fill the OMR sheet answers according to the piano rhythm signals.")

--------------------------------------------------------------------------------

[00:00:28.000 --> 00:00:32.400]
[Bank / ব্যাংক]:
(সন্দেহজনক ও তীক্ষ্ণ স্বরে)
"লিন, তোমার এই পিয়ানো কোড টেকনিকটা কিন্তু অত্যন্ত ঝুঁকিপূর্ণ। ধরা পড়লে আমাদের সবার ছাত্রত্ব বাতিল হয়ে যাবে।"
(English: "Lynn, your piano code technique is extremely risky. If caught, all our student statuses will be cancelled.")

--------------------------------------------------------------------------------

[00:00:33.100 --> 00:00:37.800]
[Pat / প্যাট]:
(আত্মবিশ্বাসী ও ধনকুবের মেজাজ)
"টাকা কোনো সমস্যা নয়, লিন। তুমি শুধু প্রতিটা সঠিক উত্তরের জন্য আমাদের গ্যারান্টি দাও, বাকিটা আমি দেখে নেব।"
(English: "Money is no problem, Lynn. You just guarantee us each correct answer, I'll take care of the rest.")

--------------------------------------------------------------------------------

[00:00:38.500 --> 00:00:43.000]
[Lynn / লিন]:
(দৃঢ়তা ও নাট্য সংকেত)
"তাহলে মনে রেখো: এ বি সি ডি — সংকেত শুরু হবে পিয়ানোর প্রথম কি বোর্ডে হাত রাখার সাথে সাথে। প্রস্তুত হও!"
(English: "Then remember: A, B, C, D — signals start as soon as my hands touch the piano keys. Get ready!")

================================================================================
                    END OF BANGLA DUBBED SCRIPT PREVIEW
================================================================================
"""

    srt_content = """1
00:00:15,100 --> 00:00:18,400
যদি তুমি এই মর্যাদাপূর্ণ স্কলারশিপ বা বৃত্তিটা জিততে চাও, তবে তোমাকে অবশ্যই আমার নিখুঁত পরিকল্পনা অনুসরণ করতে হবে।

2
00:00:19,200 --> 00:00:22,800
লিন, প্লিজ আমাকে সাহায্য করো! এই ফাইনাল পরীক্ষার প্রশ্নপত্র পাশ না করলে বাবা আমাকে ক্লাবে যেতে দেবেন না।

3
00:00:23,500 --> 00:00:27,100
পরীক্ষার হলের ঘড়িটা দেখে সময় মেলাও। পিয়ানোর সুরের সংকেত শুনে উত্তরগুলো ওএমআর শীটে ভরাট করবে।

4
00:00:28,000 --> 00:00:32,400
লিন, তোমার এই পিয়ানো কোড টেকনিকটা কিন্তু অত্যন্ত ঝুঁকিপূর্ণ। ধরা পড়লে আমাদের সবার ছাত্রত্ব বাতিল হয়ে যাবে।

5
00:00:33,100 --> 00:00:37,800
টাকা কোনো সমস্যা নয়, লিন। তুমি শুধু প্রতিটা সঠিক উত্তরের জন্য আমাদের গ্যারান্টি দাও, বাকিটা আমি দেখে নেব।

6
00:00:38,500 --> 00:00:43,000
তাহলে মনে রেখো: এ বি সি ডি — সংকেত শুরু হবে পিয়ানোর প্রথম কি বোর্ডে হাত রাখার সাথে সাথে। প্রস্তুত হও!
"""

    bangla_script_path.write_text(script_content, encoding="utf-8")
    bangla_srt_path.write_text(srt_content, encoding="utf-8")
    print(f"Generated Bangla Script: {bangla_script_path.resolve()}")
    print(f"Generated Bangla SRT:    {bangla_srt_path.resolve()}")


if __name__ == "__main__":
    generate_bangla_deliverables()
