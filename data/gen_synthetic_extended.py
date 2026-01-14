#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
扩展的合成文本图像数据生成器
支持更多东南亚和东亚语言，每语言 N=20 张，每张≥50词/字符附近的段落长度，UTF-8。
使用 Noto 字体保证跨语言字形。
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap
import random
import json

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'benchmarks' / 'synthetic'
OUT.mkdir(parents=True, exist_ok=True)

# 扩展的语言样本库
LANG_SAMPLES = {
    # 东亚语言
    'zh': [
        '傍晚下班后，我在地铁口看到一个卖花的小姑娘，手里捧着满满一束雏菊。',
        '她问："哥哥，要不要买一朵？今天的花开得特别好。"我笑着点头。',
        '回到家时，锅里正咕嘟咕嘟地炖着汤，窗外雨点跳在阳台的绿萝上。',
        '我们围着餐桌聊起周末的计划——去郊外露营，带上咖啡和新买的帐篷。',
        '临睡前，她忽然问："你有没有什么想实现的小愿望？"我说有，很多。'
    ],
    'zh-Hant': [
        '傍晚下班後，我在地鐵口看到一個賣花的小姑娘，手裡捧著滿滿一束雛菊。',
        '她問：「哥哥，要不要買一朵？今天的花開得特別好。」我笑著點頭。',
        '回到家時，鍋裡正咕嘟咕嘟地燉著湯，窗外雨點跳在陽台的綠蘿上。',
        '我們圍著餐桌聊起週末的計劃——去郊外露營，帶上咖啡和新買的帳篷。',
        '臨睡前，她忽然問：「你有沒有什麼想實現的小願望？」我說有，很多。'
    ],
    'ja': [
        '夕方、駅前のベンチで彼は紙コップのコーヒーを温めるように両手で包んだ。',
        '「ねえ、明日の朝市に行かない？」彼女は小さく笑ってうなずいた。',
        '帰り道、傘に当たる雨の音が静かなリズムになって、二人は同じ歩幅で歩いた。',
        '部屋に戻ると、窓の向こうで猫が伸びをしていて、湯気がやさしく灯りに揺れた。',
        '「願い事、ひとつだけ叶うなら？」彼は少し考えてから、そっと答えた。'
    ],
    'ko': [
        '퇴근길 편의점 앞에서 따뜻한 호빵을 사 들고, 나는 천천히 집 쪽으로 걸었다.',
        '"내일 아침 일찍 산책 갈래?" 그녀가 묻자, 나는 미소로 대답을 대신했다.',
        '비가 간간이 떨어지고, 가로등 아래 고양이는 꼬리를 말아 올린 채 앉아 있었다.',
        '집에 도착하니 전기포트가 보글거리며 물을 데우고, 창가 화분에 물방울이 매달렸다.',
        '"소원 하나만 빌 수 있다면?" 잠시 생각하다가, 나는 조용히 고개를 끄덕였다.'
    ],
    'mn': [
        'Ажлын дараа би гэртээ явах замдаа цэцэг худалдагч охинтой таарчээ.',
        '"Ах, цэцэг худалдаж авъя гэж үү?" тэр асуухад би инээмсэглэн толгой дохив.',
        'Гэртээ ирэхэд тогооны дотор шөл буцалж байлаа, цонхны гадна бороо орж байв.',
        'Бид оройн хоолны ширээний эргэн тойронд дараагийн амралтын төлөвлөгөө ярьж байв.',
        '"Хэрэв нэг зүйл хүсэх боломжтой бол юу хүсэх вэ?" тэр асуухад би бодож хариулав.'
    ],
    
    # 东南亚语言
    'th': [
        'หลังเลิกงานฉันแวะร้านข้าวแกงหน้าปากซอย กลิ่นต้มยำลอยออกมาต้อนรับเหมือนทุกวัน.',
        'พรุ่งนี้ไปตลาดเช้ากันไหม เธอยิ้มแล้วพยักหน้าเบา ๆ.',
        'ฝนโปรยลงเบา ๆ ตามทางเท้า แมวข้างบ้านขดตัวอยู่ใต้หลังคาอย่างสบายใจ.',
        'กลับถึงห้อง ไอน้ำจากหม้อต้มน้ำลอยขึ้นสะท้อนแสงไฟ สีเขียวของต้นไม้ริมหน้าต่างดูสดใส.',
        'ถ้าอธิษฐานได้ข้อเดียว เธอจะขออะไร ฉันนิ่งคิด ก่อนยิ้มรับอย่างเรียบง่าย.'
    ],
    'vi': [
        'Chiều muộn tôi dừng lại trước quán cà phê góc phố, mùi bánh mì vừa nướng lan ra ấm áp.',
        'Mai mình ra chợ sớm nhé? cô ấy hỏi khẽ, tôi mỉm cười gật đầu.',
        'Mưa rơi lất phất trên ô, con mèo bên hiên cuộn mình nằm im.',
        'Về đến nhà, ấm đun nước khẽ kêu, hơi nước bay qua khung cửa sổ.',
        'Nếu chỉ có một điều ước, cô ấy nói, tôi ngẫm nghĩ rồi trả lời thật nhỏ.'
    ],
    'my': [
        'အလုပ်ပြီးတဲ့နောက် ကော်ဖီဆိုင်ရှေ့မှာ ရပ်လိုက်တယ်၊ ပေါင်မုန့်နံ့က နွေးထွေးတဲ့အနံ့ပါ။',
        'မနက်ဖန် ဈေးစောစောသွားမလား သူမမေးတယ်၊ ငါပြုံးပြီး ခေါင်းညိတ်တယ်။',
        'မိုးရွာနေတဲ့အခါ ထီးပေါ်မှာ မိုးစက်တွေကျနေတယ်၊ လမ်းမီးတိုင်အောက်မှာ ကြောင်လေးတွေရှိနေတယ်။',
        'အိမ်ပြန်ရောက်တဲ့အခါ ရေနွေးအိုးက ဆူနေတယ်၊ ရေငွေ့တွေက ပြတင်းပေါက်ကနေ ထွက်နေတယ်။',
        'ဆုတစ်ခုပဲ တောင်းလို့ရရင် ဘာတောင်းမလဲ သူမမေးတယ်၊ ငါစဉ်းစားပြီး ဖြေလိုက်တယ်။'
    ],
    'km': [
        'បន្ទាប់ពីធ្វើការហើយ ខ្ញុំបានឈប់នៅហាងកាហ្វេមួយ ក្លិននំបុ័ងដែលទើបដុតហើយ ក្លិនក្តៅ។',
        'ថ្ងៃស្អែកទៅផ្សារព្រឹកទេ? នាងសួរដោយស្ងាត់ ខ្ញុំញញឹមហើយក្តាត់ក្បាល។',
        'ភ្លៀងធ្លាក់ចុះដោយស្ងាត់ នៅលើឆត្រក្បាល ឆ្មានៅក្រោមចង្កៀងផ្លូវ កោងខ្លួននៅក្រោមដំបូល។',
        'វិលមកផ្ទះ ឆ្នាំងរំងាស់ដោយស្ងាត់ ចំហាយទឹកហើយឆ្លងកាត់បង្អួច។',
        'បើមានបំណងមួយគត់ នាងនិយាយ ខ្ញុំគិតហើយឆ្លើយដោយស្ងាត់។'
    ],
    'lo': [
        'ຫຼັງຈາກເຮັດວຽກແລ້ວ ຂ້ອຍຢືນຢູ່ຫນ້າຮ້ານກາເຟ ກິ່ນຂະຫນົມປັງທີ່ອົບໃໝ່ ກິ່ນອົບອຸ່ນ.',
        'ມື້ອື່ນໄປຕະຫຼາດເຊົ້າບໍ? ນາງຖາມຄ່ອຍໆ ຂ້ອຍຍິ້ມແລ້ວກະເທີງຫົ ວ.',
        'ຝົນຕົກລົງຄ່ອຍໆ ຢູ່ເທິງຮົ່ມ ແມວຢູ່ຂ້າງບ້ານ ກອບຕົວຢູ່ເທິງຫລັງຄາ.',
        'ກັບເຖິງບ້ານ ໝໍ້ຕົ້ມນ້ໍາຮ້ອງຄ່ອຍໆ ຄວາມອົບອຸ່ນລອຍຜ່ານປ່ອງຢ້ຽມ.',
        'ຖ້າມີຄວາມປາດຖະຫນາຢ່າງດຽວ ນາງເວົ້າ ຂ້ອຍຄິດແລ້ວຕອບຄ່ອຍໆ.'
    ],
    'id': [
        'Sore hari aku singgah di warung sudut jalan; aroma sup tomat terasa seperti lagu lama.',
        'Besok ke pasar pagi, ya? katanya, dan aku mengangguk sambil tersenyum.',
        'Hujan mengetuk payung pelan, kucing di bawah lampu jalan meringkuk hangat.',
        'Sesampainya di rumah, ketel berdesis; uap melintas di jendela dapur.',
        'Jika punya satu harapan, dia berbisik; aku terdiam sejenak lalu menjawab pelan.'
    ],
    'ms': [
        'Petang hari aku singgah di warung sudut jalan; bau sup tomato terasa macam lagu lama.',
        'Esok pergi pasar pagi, ya? dia cakap, dan aku angguk sambil senyum.',
        'Hujan ketuk payung perlahan, kucing bawah lampu jalan meringkuk hangat.',
        'Sampai rumah, cerek berdesis; wap lintas di tingkap dapur.',
        'Kalau ada satu harapan, dia bisik; aku diam sekejap lepas tu jawab perlahan.'
    ],
    'tl': [
        'Pagkatapos ng trabaho, tumigil ako sa sulok na kainan; amoy ng sopas na kamatis parang lumang kanta.',
        'Bukas sa umaga tayo sa palengke, oo? tanong niya, at tumango ako na nakangiti.',
        'Umuulan nang mahina sa payong, pusa sa ilalim ng poste ay nakaikot na mainit.',
        'Pagdating sa bahay, kumukulo ang takure; singaw ay dumadaan sa bintana ng kusina.',
        'Kung may isang hiling lang, bulong niya; tumahimik ako sandali tapos sumagot nang mahina.'
    ],
    
    # 南亚语言
    'hi': [
        'काम के बाद मैं कोने की दुकान पर रुका; टमाटर सूप की गंध पुराने गाने जैसी लगी।',
        'कल सुबह बाजार चलें? उसने पूछा, और मैं मुस्कुराते हुए सिर हिलाया।',
        'बारिश छतरी पर धीरे से बरस रही थी, स्ट्रीट लैंप के नीचे बिल्ली गर्मजोशी से सिकुड़ी हुई थी।',
        'घर पहुंचकर केतली सीटी बजा रही थी; भाप रसोई की खिड़की से गुजर रही थी।',
        'अगर एक ही इच्छा हो, उसने फुसफुसाया; मैं कुछ देर चुप रहा फिर धीरे से जवाब दिया।'
    ],
    'bn': [
        'কাজের পর আমি কোণার দোকানে থামলাম; টমেটো স্যুপের গন্ধ পুরানো গানের মতো লাগছিল।',
        'কাল সকালে বাজারে যাবো? সে জিজ্ঞেস করল, আর আমি হেসে মাথা নাড়লাম।',
        'বৃষ্টি ছাতায় ধীরে ধীরে পড়ছিল, রাস্তার বাতির নিচে বিড়াল গরমজোশে কুঁকড়ে ছিল।',
        'বাড়ি পৌঁছে কেটলি সিঁড়ি বাজাচ্ছিল; বাষ্প রান্নাঘরের জানালা দিয়ে যাচ্ছিল।',
        'যদি একটা ইচ্ছা থাকে, সে ফিসফিস করল; আমি কিছুক্ষণ চুপ থেকে তারপর ধীরে উত্তর দিলাম।'
    ],
    'ur': [
        'کام کے بعد میں کونے کی دکان پر رکا؛ ٹماٹر سوپ کی بو پرانے گانے جیسی لگ رہی تھی۔',
        'کل صبح بازار چلیں؟ اس نے پوچھا، اور میں مسکراتے ہوئے سر ہلایا۔',
        'بارش چھتری پر آہستہ سے برس رہی تھی، سٹریٹ لیمپ کے نیچے بلی گرمجوشی سے سکڑی ہوئی تھی۔',
        'گھر پہنچ کر کیتلی سیٹی بجا رہی تھی؛ بھاپ باورچی خانے کی کھڑکی سے گزر رہی تھی۔',
        'اگر ایک ہی خواہش ہو، اس نے پھسپھسایا؛ میں کچھ دیر چپ رہا پھر آہستہ سے جواب دیا۔'
    ],
    'ta': [
        'வேலை முடிந்த பிறகு நான் மூலையில் உள்ள கடையில் நின்றேன்; தக்காளி சூப்பின் வாசனை பழைய பாட்டு போல இருந்தது.',
        'நாளை காலை சந்தைக்கு போகலாமா? அவள் கேட்டாள், நான் சிரித்துக்கொண்டே தலையை ஆட்டினேன்.',
        'மழை குடையில் மெதுவாக விழுந்துகொண்டிருந்தது, தெரு விளக்கின் கீழ் பூனை சூடாக சுருண்டு கிடந்தது.',
        'வீட்டுக்கு வந்ததும் கெட்டில் சீட்டி அடித்துக்கொண்டிருந்தது; நீராவி சமையலறை ஜன்னல் வழியாக சென்றுகொண்டிருந்தது.',
        'ஒரு ஆசை மட்டும் இருந்தால், அவள் முணுமுணுத்தாள்; நான் சிறிது நேரம் அமைதியாக இருந்துவிட்டு பிறகு மெதுவாக பதிலளித்தேன்.'
    ],
    'te': [
        'పని ముగిసిన తర్వాత నేను మూలలోని దుకాణం వద్ద ఆగాను; టమాటర్ సూప్ వాసన పాత పాటలా అనిపించింది.',
        'రేపు ఉదయం మార్కెట్ కి వెళ్ళుదామా? ఆమె అడిగింది, నేను నవ్వుతూ తల ఊపాను.',
        'వర్షం గొడుగుపై మెల్లగా కురుస్తోంది, వీధి దీపం క్రింద పిల్లి వేడిగా చుట్టుకొని ఉంది.',
        'ఇంటికి చేరుకున్న తర్వాత కెటిల్ సీటీ వేస్తోంది; ఆవిరి వంటగది కిటికీ గుండా వెళుతోంది.',
        'ఒక్క కోరిక మాత్రమే ఉంటే, ఆమె గుసగుసలాడింది; నేను కొంతసేపు నిశ్శబ్దంగా ఉండి తర్వాత మెల్లగా జవాబిచ్చాను.'
    ],
    'kn': [
        'ಕೆಲಸ ಮುಗಿದ ನಂತರ ನಾನು ಮೂಲೆಯ ಅಂಗಡಿಯಲ್ಲಿ ನಿಂತೆ; ಟೊಮಾಟೊ ಸೂಪ್ ವಾಸನೆ ಹಳೆಯ ಹಾಡಿನಂತೆ ಅನಿಸಿತು.',
        'ನಾಳೆ ಬೆಳಿಗ್ಗೆ ಮಾರುಕಟ್ಟೆಗೆ ಹೋಗೋಣವೇ? ಅವಳು ಕೇಳಿದಳು, ನಾನು ನಗುತ್ತಾ ತಲೆ ಅಲ್ಲಾಡಿಸಿದೆ.',
        'ಮಳೆ ಕೊಡಗಿನ ಮೇಲೆ ನಿಧಾನವಾಗಿ ಸುರಿಯುತ್ತಿತ್ತು, ರಸ್ತೆ ದೀಪದ ಕೆಳಗೆ ಬೆಕ್ಕು ಬಿಸಿಯಾಗಿ ಸುರುಳಿ ಸುತ್ತಿತ್ತು.',
        'ಮನೆಗೆ ಬಂದ ನಂತರ ಕೆಟಲ್ ಸೀಟಿ ಹಾಕುತ್ತಿತ್ತು; ಆವಿ ಅಡುಗೆಮನೆ ಕಿಟಕಿಯ ಮೂಲಕ ಹಾದುಹೋಗುತ್ತಿತ್ತು.',
        'ಒಂದು ಆಸೆ ಮಾತ್ರ ಇದ್ದರೆ, ಅವಳು ಗುಸಗುಸಲಾಡಿದಳು; ನಾನು ಸ್ವಲ್ಪ ಹೊತ್ತು ಮೌನವಾಗಿ ನಿಂತು ನಂತರ ನಿಧಾನವಾಗಿ ಉತ್ತರಿಸಿದೆ.'
    ],
    'ml': [
        'ജോലി കഴിഞ്ഞതിന് ശേഷം ഞാൻ മൂലയിലെ കടയിൽ നിന്നു; ടൊമാറ്റോ സൂപ്പിന്റെ മണം പഴയ പാട്ട് പോലെ തോന്നി.',
        'നാളെ രാവിലെ മാർക്കറ്റിലേക്ക് പോകാമോ? അവൾ ചോദിച്ചു, ഞാൻ ചിരിച്ചുകൊണ്ട് തല ആടിച്ചു.',
        'മഴ കുടയിൽ മെല്ലെ പെയ്തുകൊണ്ടിരുന്നു, തെരുവ് വിളക്കിന് കീഴിൽ പൂച്ച ചൂടായി ചുരുണ്ടുകിടന്നു.',
        'വീട്ടിൽ എത്തിയപ്പോൾ കെട്ടിൽ സീറ്റി അടിച്ചുകൊണ്ടിരുന്നു; നീരാവി അടുക്കള ജാലകത്തിലൂടെ കടന്നുപോയി.',
        'ഒരു ആഗ്രഹം മാത്രമേ ഉണ്ടായിരുന്നുള്ളൂ, അവൾ മന്ത്രിച്ചു; ഞാൻ കുറച്ച് നേരം മിണ്ടാതെ നിന്നു പിന്നെ മെല്ലെ മറുപടി പറഞ്ഞു.'
    ],
    'si': [
        'කාර්යය අවසන් වූ පසු මම කොනේ ගබඩාව අසල නැවතීමි; තක්කාලි සුප් ගඳ පැරණි ගීතයක් වගේ හැඟුණා.',
        'හෙට උදේ වෙළඳපොළට යමුද? ඇය ඇසුවා, මම සිනහවෙන් හිස ගසා.',
        'වැස්ස කුඩය මත මෘදුව පතිත වූවා, වීදි ලාම්පුව යට බළලා උණුසුම්ව ගැලී සිටියා.',
        'ගෙදර ලඟා වූ විට කේටල් සීටි ගසමින් සිටියා; වාෂ්පය මුළුතැන්ගෙයි කවුළුව හරහා ගමන් කරමින් සිටියා.',
        'එක ආශාවක් පමණක් තිබුණේ නම්, ඇය ගුස්ගුස් කළා; මම මොහොතක් නිහඬව සිට පසුව මෘදුව පිළිතුරු දුන්නා.'
    ],
    'ne': [
        'काम सकिएपछि म घरको कुनामा रोकिए; टमाटर सूपको गन्ध पुरानो गीत जस्तो लाग्यो।',
        'भोलि बिहान बजार जाने? उनले सोधिन्, र म मुस्कुराउँदै टाउको हल्लाए।',
        'पानी छातामा मृदु रूपमा खसिरहेको थियो, सडकको बत्तीमुनि बिरालो तातो रूपमा घुमिरहेको थियो।',
        'घर पुगेपछि केटल सिटी बजाउँदै थियो; भाप रसोईघरको झ्यालबाट जाँदै थियो।',
        'एक मात्र इच्छा भए, उनले फुसफुसाए; म केही क्षण चुप लागे र त्यसपछि मृदु रूपमा जवाफ दिए।'
    ],
    
    # 欧洲语言
    'en': [
        'After work I stopped by the corner diner; the smell of tomato soup felt like an old song.',
        '"Shall we visit the morning market tomorrow?" she asked, and I nodded with a grin.',
        'Rain tapped gently on the umbrella, and the cat by the lamppost curled into a comma.',
        'Back home, the kettle hummed; steam drifted across the window where the pothos climbed.',
        '"If you had one wish," she said. I paused, then answered softly in the quiet kitchen.'
    ],
    'fr': [
        'Après le travail, je me suis arrêté au coin de rue; l\'odeur de la soupe aux tomates ressemblait à une vieille chanson.',
        '"Irons-nous au marché du matin demain?" demanda-t-elle, et je hochai la tête avec un sourire.',
        'La pluie tapait doucement sur le parapluie, et le chat près du lampadaire se recroquevillait en virgule.',
        'De retour à la maison, la bouilloire ronronnait; la vapeur dérivait à travers la fenêtre où le pothos grimpait.',
        '"Si tu avais un seul vœu," dit-elle. Je m\'arrêtai, puis répondis doucement dans la cuisine silencieuse.'
    ],
    'de': [
        'Nach der Arbeit blieb ich an der Ecke stehen; der Geruch von Tomatensuppe fühlte sich wie ein altes Lied an.',
        '"Sollen wir morgen früh zum Markt gehen?" fragte sie, und ich nickte mit einem Grinsen.',
        'Regen klopfte sanft auf den Schirm, und die Katze am Laternenpfahl rollte sich zu einem Komma zusammen.',
        'Zu Hause summte der Wasserkocher; Dampf trieb über das Fenster, wo die Pothos kletterte.',
        '"Wenn du einen Wunsch hättest," sagte sie. Ich hielt inne, dann antwortete ich leise in der stillen Küche.'
    ],
    'es': [
        'Después del trabajo me detuve en la esquina; el olor de la sopa de tomate se sentía como una canción antigua.',
        '"¿Iremos al mercado matutino mañana?" preguntó, y asentí con una sonrisa.',
        'La lluvia golpeaba suavemente el paraguas, y el gato junto al poste se enroscaba en una coma.',
        'De vuelta a casa, la tetera zumbaba; el vapor se deslizaba por la ventana donde trepaba la pothos.',
        '"Si tuvieras un deseo," dijo. Me detuve, luego respondí suavemente en la cocina silenciosa.'
    ],
    'ru': [
        'После работы я остановился на углу; запах томатного супа напоминал старую песню.',
        '"Пойдем завтра утром на рынок?" спросила она, и я кивнул с улыбкой.',
        'Дождь мягко стучал по зонту, а кот у фонарного столба свернулся в запятую.',
        'Дома чайник гудел; пар дрейфовал через окно, где карабкался потос.',
        '"Если бы у тебя было одно желание," сказала она. Я замолчал, затем тихо ответил в тихой кухне.'
    ],
    
    # 中东语言
    'ar': [
        'بعد العمل توقفت عند الزاوية؛ رائحة حساء الطماطم كانت مثل أغنية قديمة.',
        '"هل سنذهب إلى السوق صباحاً غداً؟" سألت، وأومأت برأسي مبتسماً.',
        'المطر ينقر بلطف على المظلة، والقطة بجانب عمود الإنارة تتكور كفاصلة.',
        'في المنزل، الغلاية تطن؛ البخار ينجرف عبر النافذة حيث يتسلق البوثوس.',
        '"لو كان لديك أمنية واحدة،" قالت. توقفت، ثم أجبت بهدوء في المطبخ الهادئ.'
    ],
    'fa': [
        'بعد کار در گوشه توقف کردم؛ بوی سوپ گوجه‌فرنگی مثل آهنگ قدیمی بود.',
        '"فردا صبح به بازار برویم؟" پرسید، و من با لبخند سر تکان دادم.',
        'باران نرم روی چتر می‌زد، و گربه کنار تیر چراغ مثل ویرگول جمع شده بود.',
        'در خانه، کتری زمزمه می‌کرد؛ بخار از پنجره عبور می‌کرد جایی که پوتوس بالا می‌رفت.',
        '"اگر یک آرزو داشتی،" گفت. مکث کردم، سپس در آشپزخانه ساکت آرام پاسخ دادم.'
    ]
}

def generate_variant(lang: str, idx: int, target_words: int = 50) -> str:
    """生成语言变体文本"""
    rnd = random.Random(hash((lang, idx)) & 0xffffffff)
    bank = LANG_SAMPLES[lang]
    words: list[str] = []
    
    # 连接词库
    connectors = {
        'zh': ['然后', '后来', '不过', '于是', '同时'],
        'zh-Hant': ['然後', '後來', '不過', '於是', '同時'],
        'ja': ['そして', 'それから', 'しかし', 'つまり', '同時に'],
        'ko': ['그리고', '그러나', '그러면서', '한편', '이어서'],
        'mn': ['Тэгээд', 'Дараа нь', 'Гэхдээ', 'Үүнтэй зэрэгцээд', 'Эцэст нь'],
        'th': ['แล้ว', 'จากนั้น', 'แต่ว่า', 'พร้อมกันนั้น', 'ในขณะเดียวกัน'],
        'vi': ['Rồi', 'Sau đó', 'Tuy nhiên', 'Cùng lúc ấy', 'Cuối cùng'],
        'my': ['ပြီးတော့', 'အဲ့ဒီနောက်', 'ဒါပေမယ့်', 'အဲ့ဒီအချိန်မှာ', 'နောက်ဆုံးမှာ'],
        'km': ['បន្ទាប់មក', 'ពីនោះ', 'ប៉ុន្តែ', 'ក្នុងពេលដែល', 'ចុងក្រោយ'],
        'lo': ['ຫຼັງຈາກນັ້ນ', 'ຈາກນັ້ນ', 'ແຕ່', 'ໃນຂະນະດຽວກັນ', 'ສຸດທ້າຍ'],
        'id': ['Lalu', 'Setelah itu', 'Namun', 'Sementara itu', 'Akhirnya'],
        'ms': ['Lepas tu', 'Selepas tu', 'Tapi', 'Sementara tu', 'Akhirnya'],
        'tl': ['Tapos', 'Pagkatapos', 'Pero', 'Samantala', 'Sa huli'],
        'hi': ['फिर', 'उसके बाद', 'लेकिन', 'उसी समय', 'अंत में'],
        'bn': ['তারপর', 'এর পর', 'কিন্তু', 'একই সময়ে', 'শেষে'],
        'ur': ['پھر', 'اس کے بعد', 'لیکن', 'اسی وقت', 'آخر میں'],
        'ta': ['பிறகு', 'அதன் பிறகு', 'ஆனால்', 'அதே நேரத்தில்', 'இறுதியில்'],
        'te': ['అప్పుడు', 'దాని తర్వాత', 'కానీ', 'అదే సమయంలో', 'చివరికి'],
        'kn': ['ನಂತರ', 'ಅದರ ನಂತರ', 'ಆದರೆ', 'ಅದೇ ಸಮಯದಲ್ಲಿ', 'ಅಂತಿಮವಾಗಿ'],
        'ml': ['പിന്നെ', 'അതിന് ശേഷം', 'പക്ഷേ', 'അതേ സമയം', 'അവസാനം'],
        'si': ['පසුව', 'ඒ පසු', 'නමුත්', 'ඒ සමයේ', 'අවසානයේ'],
        'ne': ['त्यसपछि', 'यसको पछि', 'तर', 'उही समयमा', 'अन्त्यमा'],
        'en': ['Then', 'Afterwards', 'However', 'Meanwhile', 'Eventually'],
        'fr': ['Puis', 'Ensuite', 'Cependant', 'Pendant ce temps', 'Finalement'],
        'de': ['Dann', 'Danach', 'Jedoch', 'Währenddessen', 'Schließlich'],
        'es': ['Luego', 'Después', 'Sin embargo', 'Mientras tanto', 'Finalmente'],
        'ru': ['Затем', 'После этого', 'Однако', 'Тем временем', 'В конце концов'],
        'ar': ['ثم', 'بعد ذلك', 'لكن', 'في الوقت نفسه', 'في النهاية'],
        'fa': ['سپس', 'بعد از آن', 'اما', 'در همین حال', 'در نهایت']
    }.get(lang, [''])
    
    k = min(len(bank), rnd.randint(5, 7))
    idxs = list(range(len(bank)))
    rnd.shuffle(idxs)
    idxs = idxs[:k]
    
    for j, ix in enumerate(idxs):
        base = bank[ix]
        # 为某些语言添加引号
        if lang not in ['th', 'my', 'km', 'lo'] and rnd.random() < 0.3:
            if lang in ['zh', 'zh-Hant']:
                base = f'"{base}"'
            elif lang == 'ja':
                base = f'「{base}」'
            elif lang == 'ko':
                base = f'"{base}"'
            else:
                base = f'"{base}"'
        
        if j > 0 and connectors:
            joiner = rnd.choice(connectors)
            words.append(joiner + ' ' + base)
        else:
            words.append(base)
        
        if len(' '.join(words).split()) >= target_words:
            break
    
    return ' '.join(words)

def get_font(lang: str, size: int = 28) -> ImageFont.FreeTypeFont:
    """获取适合语言的字体"""
    if lang == 'th':
        candidates = [
            str((OUT.parent / 'fonts' / 'NotoSansThai-Regular.ttf').resolve()),
            str((OUT.parent / 'fonts' / 'NotoSerifThai-Regular.ttf').resolve()),
            '/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansThaiLooped-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
        ]
    elif lang in ('zh', 'zh-Hant', 'ja', 'ko'):
        candidates = [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
        ]
    elif lang in ('hi', 'bn', 'ur', 'ta', 'te', 'kn', 'ml', 'si', 'ne'):
        candidates = [
            '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
        ]
    elif lang in ('ar', 'fa'):
        candidates = [
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
        ]
    else:
        candidates = [
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        ]
    
    for p in candidates:
        fp = Path(p)
        if fp.exists():
            try:
                return ImageFont.truetype(str(fp), size)
            except Exception:
                continue
    
    return ImageFont.load_default()

def render_paragraph(text: str, font: ImageFont.ImageFont, width: int = 1200) -> Image:
    """渲染段落文本为图像"""
    margin = 32
    wrapper = textwrap.TextWrapper(width=36)
    lines = wrapper.wrap(text)
    line_h = font.getbbox('A')[3] - font.getbbox('A')[1] + 8
    height = margin * 2 + line_h * max(6, len(lines))
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    y = margin
    for line in lines:
        draw.text((margin, y), line, fill=(0, 0, 0), font=font)
        y += line_h
    return img

def main(n_per_lang: int = 20, langs: list[str] | None = None):
    """主函数"""
    manifest = []
    lang_items = LANG_SAMPLES.items() if not langs else [(l, LANG_SAMPLES[l]) for l in langs if l in LANG_SAMPLES]
    
    print(f"🌏 开始生成扩展的合成数据集...")
    print(f"📊 支持语言: {len(LANG_SAMPLES)} 种")
    print(f"📈 每种语言样本数: {n_per_lang}")
    
    for lang, _ in lang_items:
        print(f"📝 生成 {lang} 语言数据...")
        lang_dir = OUT / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        font = get_font(lang)
        
        for i in range(n_per_lang):
            text = generate_variant(lang, i, target_words=50)
            img = render_paragraph(text, font)
            path = lang_dir / f'{lang}_{i:02d}.png'
            img.save(path)
            manifest.append({'language': lang, 'path': str(path), 'tokens_est': len(text.split())})
        
        print(f"✅ {lang}: {n_per_lang} 个样本完成")
    
    # 保存清单文件
    out = OUT / 'manifest.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 扩展合成数据生成完成!")
    print(f"📁 输出目录: {OUT}")
    print(f"📄 清单文件: {out}")
    print(f"📊 总样本数: {len(manifest)}")
    print(f"🌏 支持语言: {len(set(item['language'] for item in manifest))} 种")

if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='生成扩展的多语言合成数据集')
    ap.add_argument('--n', type=int, default=20, help='每种语言的样本数')
    ap.add_argument('--langs', type=str, default='', help='指定语言列表，用逗号分隔')
    args = ap.parse_args()
    
    langs = [s.strip() for s in args.langs.split(',') if s.strip()] if args.langs else None
    main(n_per_lang=args.n, langs=langs)



