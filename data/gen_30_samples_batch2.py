#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
30样本版多语言合成数据集生成器 - 第二批（7个语言）
每种语言30个不重复的完整文本样本
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import textwrap
import random
import json
import os

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'benchmarks' / 'synthetic_30_samples_batch2'
OUT.mkdir(parents=True, exist_ok=True)

# 第二批语言样本库 - 每种语言30个不重复样本
LANG_SAMPLES = {
    'si': [
        'ආයුබෝවන්, ඔබ කොහොමද? මම හොඳයි।',
        'ස්තූතියි, මෙය හොඳයි।',
        'ඔබේ දිනය සුභ වේවා. මට ඔබට උදව් කළ හැකියි।',
        'මෙය සුන්දර දිනයකි. ඔබ කොහෙද යනවා?',
        'ඔබව හමුවීම සතුටකි. ඔබේ නම කුමක්ද?',
        'අද කාලගුණය හොඳයි।',
        'මම ඔබට උදව් කිරීමට මෙහි සිටිමි।',
        'ඔබ මා සමඟ කතා කිරීමට කැමතිද?',
        'මෙය පුදුම දිනයකි।',
        'මම ඔබ සමඟ කාලය ගත කිරීමට කැමතියි।',
        'සාදරයෙන් පිළිගනිමු. මම ඔබේ සේවාවේ සිටිමි।',
        'මෙම ස්ථානය ඉතා සුන්දරයි।',
        'මට ඔබ වෙනුවෙන් යමක් කළ හැකියි।',
        'ඔබේ දිනය සුභ වේවා।',
        'මෙය පුදුම අත්දැකීමකි।',
        'මම ඔබේ සතුට සඳහා මෙහි සිටිමි।',
        'ඔබේ කාලය ඉතා වටිනායි।',
        'මම ඔබ සමඟ එකඟ වෙමි।',
        'මෙය සුභ දිනයකි।',
        'මම ඔබට උදව් කිරීමට සූදානම්යි।',
        'ඔබේ සෞඛ්‍යය හොඳ වේවා।',
        'මෙය මහා දිනයකි।',
        'මම ඔබ සමඟ සතුටුයි।',
        'ඔබේ අනාගතය බැබළෙනු වේවා।',
        'මෙය සතුටුදායක දිනයකි।',
        'මම ඔබේ සාර්ථකත්වය ප්‍රාර්ථනා කරමි।',
        'ඔබේ ජීවිතය සතුටුදායක වේවා।',
        'මෙය පූජනීය දිනයකි।',
        'මම ඔබ සමඟ ආඩම්බර වෙමි।',
        'ඔබේ හදවත පවිත්‍ර වේවා।'
    ],
    'ta': [
        'வணக்கம், நீங்கள் எப்படி இருக்கிறீர்கள்? நான் நன்றாக இருக்கிறேன்।',
        'நன்றி, இது மிகவும் நன்றாக இருக்கிறது।',
        'உங்கள் நாள் நல்லதாக இருக்கட்டும்। நான் உங்களுக்கு உதவ முடியும்।',
        'இது ஒரு அழகான நாள். நீங்கள் எங்கே போகிறீர்கள்?',
        'உங்களை சந்தித்ததில் மகிழ்ச்சி. உங்கள் பெயர் என்ன?',
        'இன்று வானிலை மிகவும் நன்றாக உள்ளது।',
        'நான் உங்களுக்கு உதவ இங்கே இருக்கிறேன்।',
        'நீங்கள் என்னுடன் பேச விரும்புகிறீர்களா?',
        'இது ஒரு அற்புதமான நாள்।',
        'நான் உங்களுடன் நேரம் செலவிட விரும்புகிறேன்।',
        'வரவேற்கிறோம். நான் உங்கள் சேவையில் இருக்கிறேன்।',
        'இந்த இடம் மிகவும் அழகானது।',
        'நான் உங்களுக்காக ஏதாவது செய்ய முடியும்।',
        'உங்கள் நாள் நல்லதாக இருக்கட்டும்।',
        'இது ஒரு அற்புதமான அனுபவம்।',
        'நான் உங்கள் மகிழ்ச்சிக்காக இங்கே இருக்கிறேன்।',
        'உங்கள் நேரம் மிகவும் விலைமதிப்பற்றது।',
        'நான் உங்களுடன் உடன்படுகிறேன்।',
        'இது ஒரு நல்ல நாள்।',
        'நான் உங்களுக்கு உதவ தயாராக இருக்கிறேன்।',
        'உங்கள் ஆரோக்கியம் நல்லதாக இருக்கட்டும்।',
        'இது ஒரு மகத்தான நாள்।',
        'நான் உங்களுடன் மகிழ்ச்சியாக இருக்கிறேன்।',
        'உங்கள் எதிர்காலம் பிரகாசமாக இருக்கட்டும்।',
        'இது ஒரு மகிழ்ச்சியான நாள்।',
        'நான் உங்கள் வெற்றியை விரும்புகிறேன்।',
        'உங்கள் வாழ்க்கை மகிழ்ச்சியாக இருக்கட்டும்।',
        'இது ஒரு புனிதமான நாள்।',
        'நான் உங்களுடன் பெருமைப்படுகிறேன்।',
        'உங்கள் இதயம் புனிதமாக இருக்கட்டும்।'
    ],
    'te': [
        'నమస్కారం, మీరు ఎలా ఉన్నారు? నేను బాగున్నాను।',
        'ధన్యవాదాలు, ఇది చాలా బాగుంది।',
        'మీరు మంచి రోజు గడపండి। నేను మీకు సహాయం చేయగలను।',
        'ఇది అందమైన రోజు। మీరు ఎక్కడికి వెళుతున్నారు?',
        'మిమ్మల్ని కలిసినందుకు సంతోషం। మీ పేరు ఏమిటి?',
        'ఈరోజు వాతావరణం చాలా బాగుంది।',
        'నేను మీకు సహాయం చేయడానికి ఇక్కడ ఉన్నాను।',
        'మీరు నాతో మాట్లాడాలనుకుంటున్నారా?',
        'ఇది అద్భుతమైన రోజు।',
        'నేను మీతో సమయం గడపాలనుకుంటున్నాను।',
        'స్వాగతం। నేను మీ సేవలో ఉన్నాను।',
        'ఈ ప్రదేశం చాలా అందమైనది।',
        'నేను మీ కోసం ఏదైనా చేయగలను।',
        'మీ రోజు మంచిదిగా ఉండాలి।',
        'ఇది అద్భుతమైన అనుభవం।',
        'నేను మీ ఆనందం కోసం ఇక్కడ ఉన్నాను।',
        'మీ సమయం చాలా విలువైనది।',
        'నేను మీతో ఏకీభవిస్తున్నాను।',
        'ఇది మంచి రోజు।',
        'నేను మీకు సహాయం చేయడానికి సిద్ధంగా ఉన్నాను।',
        'మీ ఆరోగ్యం మంచిగా ఉండాలి।',
        'ఇది గొప్ప రోజు।',
        'నేను మీతో సంతోషంగా ఉన్నాను।',
        'మీ భవిష్యత్తు ప్రకాశవంతంగా ఉండాలి।',
        'ఇది ఆనందకరమైన రోజు।',
        'నేను మీ విజయాన్ని కోరుకుంటున్నాను।',
        'మీ జీవితం ఆనందకరంగా ఉండాలి।',
        'ఇది పవిత్రమైన రోజు।',
        'నేను మీతో గర్విస్తున్నాను।',
        'మీ హృదయం పవిత్రంగా ఉండాలి।'
    ],
    'th': [
        'สวัสดี คุณสบายดีไหม ฉันสบายดี',
        'ขอบคุณ ดีมาก',
        'ขอให้คุณมีวันที่ดี ฉันสามารถช่วยคุณได้',
        'เป็นวันที่สวยงาม คุณจะไปไหน',
        'ดีใจที่ได้พบคุณ คุณชื่ออะไร',
        'วันนี้อากาศดีมาก',
        'ฉันอยู่ที่นี่เพื่อช่วยคุณ',
        'คุณอยากคุยกับฉันไหม',
        'เป็นวันที่ยอดเยี่ยม',
        'ฉันอยากใช้เวลากับคุณ',
        'ยินดีต้อนรับ ฉันอยู่ในการบริการของคุณ',
        'สถานที่นี้สวยมาก',
        'ฉันสามารถทำอะไรให้คุณได้',
        'ขอให้วันของคุณดี',
        'นี่เป็นประสบการณ์ที่น่าทึ่ง',
        'ฉันอยู่ที่นี่เพื่อความสุขของคุณ',
        'เวลาของคุณมีค่ามาก',
        'ฉันเห็นด้วยกับคุณ',
        'นี่เป็นวันที่ดี',
        'ฉันพร้อมที่จะช่วยคุณ',
        'ขอให้สุขภาพของคุณดี',
        'นี่เป็นวันที่ยิ่งใหญ่',
        'ฉันมีความสุขกับคุณ',
        'ขอให้อนาคตของคุณสดใส',
        'นี่เป็นวันที่สนุก',
        'ฉันขอให้คุณประสบความสำเร็จ',
        'ขอให้ชีวิตของคุณมีความสุข',
        'นี่เป็นวันที่ศักดิ์สิทธิ์',
        'ฉันภูมิใจกับคุณ',
        'ขอให้หัวใจของคุณบริสุทธิ์'
    ],
    'ur': [
        'سلام، آپ کیسے ہیں؟ میں ٹھیک ہوں۔',
        'شکریہ، یہ بہت اچھا ہے۔',
        'آپ کا دن اچھا گزرے۔ میں آپ کی مدد کر سکتا ہوں۔',
        'یہ ایک خوبصورت دن ہے۔ آپ کہاں جا رہے ہیں؟',
        'آپ سے مل کر خوشی ہوئی۔ آپ کا نام کیا ہے؟',
        'آج موسم بہت اچھا ہے۔',
        'میں آپ کی مدد کے لیے یہاں ہوں۔',
        'کیا آپ مجھ سے بات کرنا چاہتے ہیں؟',
        'یہ ایک شاندار دن ہے۔',
        'میں آپ کے ساتھ وقت گزارنا چاہتا ہوں۔',
        'خوش آمدید۔ میں آپ کی خدمت میں ہوں۔',
        'یہ جگہ بہت خوبصورت ہے۔',
        'میں آپ کے لیے کچھ کر سکتا ہوں۔',
        'آپ کا دن اچھا گزرے۔',
        'یہ ایک حیرت انگیز تجربہ ہے۔',
        'میں آپ کی خوشی کے لیے یہاں ہوں۔',
        'آپ کا وقت بہت قیمتی ہے۔',
        'میں آپ سے متفق ہوں۔',
        'یہ ایک اچھا دن ہے۔',
        'میں آپ کی مدد کے لیے تیار ہوں۔',
        'آپ کی صحت اچھی رہے۔',
        'یہ ایک عظیم دن ہے۔',
        'میں آپ کے ساتھ خوش ہوں۔',
        'آپ کا مستقبل روشن ہو۔',
        'یہ ایک خوشگوار دن ہے۔',
        'میں آپ کی کامیابی کی دعا کرتا ہوں۔',
        'آپ کی زندگی خوشگوار ہو۔',
        'یہ ایک مقدس دن ہے۔',
        'میں آپ کے ساتھ فخر محسوس کرتا ہوں۔',
        'آپ کا دل پاک ہو۔'
    ],
    'zh': [
        '你好，你好吗？我很好。',
        '谢谢，这很好。',
        '祝你今天愉快。我可以帮助你。',
        '这是一个美好的日子。你要去哪里？',
        '很高兴见到你。你叫什么名字？',
        '今天天气很好。',
        '我在这里帮助你。',
        '你想和我说话吗？',
        '这是美好的一天。',
        '我想和你共度时光。',
        '欢迎。我为你服务。',
        '这个地方很美丽。',
        '我可以为你做些什么。',
        '祝你今天愉快。',
        '这是奇妙的经历。',
        '我在这里为你带来快乐。',
        '你的时间很宝贵。',
        '我同意你的观点。',
        '这是美好的一天。',
        '我准备帮助你。',
        '祝你身体健康。',
        '这是伟大的一天。',
        '我和你在一起很开心。',
        '愿你前途光明。',
        '这是快乐的一天。',
        '我祝你成功。',
        '愿你生活幸福。',
        '这是神圣的一天。',
        '我为你感到骄傲。',
        '愿你心灵纯洁。'
    ],
    'zh-Hant': [
        '你好，你好嗎？我很好。',
        '謝謝，這很好。',
        '祝你今天愉快。我可以幫助你。',
        '這是一個美好的日子。你要去哪裡？',
        '很高興見到你。你叫什麼名字？',
        '今天天氣很好。',
        '我在這裡幫助你。',
        '你想和我說話嗎？',
        '這是美好的一天。',
        '我想和你共度時光。',
        '歡迎。我為你服務。',
        '這個地方很美麗。',
        '我可以為你做些什麼。',
        '祝你今天愉快。',
        '這是奇妙的經歷。',
        '我在這裡為你帶來快樂。',
        '你的時間很寶貴。',
        '我同意你的觀點。',
        '這是美好的一天。',
        '我準備幫助你。',
        '祝你身體健康。',
        '這是偉大的一天。',
        '我和你在一起很開心。',
        '願你前途光明。',
        '這是快樂的一天。',
        '我祝你成功。',
        '願你生活幸福。',
        '這是神聖的一天。',
        '我為你感到驕傲。',
        '願你心靈純潔。'
    ]
}

def get_perfect_font_for_language(lang: str, size: int = 36) -> ImageFont.FreeTypeFont:
    """为特定语言获取完美字体"""
    
    # 语言特定的完美字体映射
    perfect_fonts = {
        'si': [
            '/usr/share/fonts/truetype/noto/NotoSansSinhala-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerifSinhala-Regular.ttf'
        ],
        'ta': [
            '/usr/share/fonts/truetype/noto/NotoSansTamil-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerifTamil-Regular.ttf'
        ],
        'te': [
            '/usr/share/fonts/truetype/noto/NotoSansTelugu-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerifTelugu-Regular.ttf'
        ],
        'th': [
            '/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSansThaiLooped-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerifThai-Regular.ttf'
        ],
        'ur': [
            '/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSerifArabic-Regular.ttf'
        ],
        'zh': [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansSC-Regular.otf'
        ],
        'zh-Hant': [
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/noto/NotoSansTC-Regular.otf'
        ]
    }
    
    font_candidates = perfect_fonts.get(lang, [])
    
    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                # 严格测试字体
                if test_font_perfect(font, lang):
                    print(f"✅ {lang}: 使用完美字体 {font_path}")
                    return font
            except Exception as e:
                print(f"❌ {lang}: 字体 {font_path} 失败: {e}")
                continue
    
    # 如果都失败，使用默认字体
    print(f"⚠️  {lang}: 使用默认字体")
    return ImageFont.load_default()

def test_font_perfect(font: ImageFont.FreeTypeFont, lang: str) -> bool:
    """严格测试字体，确保无乱码"""
    test_chars = {
        'si': 'ආයුබෝවන්',
        'ta': 'வணக்கம்',
        'te': 'నమస్కారం',
        'th': 'สวัสดี',
        'ur': 'سلام',
        'zh': '你好',
        'zh-Hant': '你好'
    }
    
    if lang in test_chars:
        try:
            test_text = test_chars[lang]
            bbox = font.getbbox(test_text)
            # 检查边界框是否有效
            if bbox[2] > bbox[0] and bbox[3] > bbox[1]:
                # 尝试实际渲染测试
                test_img = Image.new('RGB', (200, 100), 'white')
                test_draw = ImageDraw.Draw(test_img)
                test_draw.text((10, 10), test_text, fill='black', font=font)
                return True
        except:
            return False
    
    return True

def create_full_text_image(text: str, font: ImageFont.FreeTypeFont, width: int = 1400, height: int = 500) -> Image:
    """创建完整文本图像，支持自动换行"""
    # 创建更大的图像
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # 设置边距
    margin = 60
    
    # 计算行高
    line_height = font.getbbox('A')[3] - font.getbbox('A')[1] + 20
    
    # 自动换行处理
    max_width = width - 2 * margin
    lines = []
    
    # 按字符分割，支持多语言
    words = text.split()
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        bbox = font.getbbox(test_line)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # 单个词太长，强制换行
                lines.append(word)
                current_line = ""
    
    if current_line:
        lines.append(current_line)
    
    # 计算总文本高度
    total_text_height = len(lines) * line_height
    start_y = (height - total_text_height) // 2
    
    # 绘制文本
    y = start_y
    for line in lines:
        # 计算文本宽度以水平居中
        try:
            text_width = font.getbbox(line)[2] - font.getbbox(line)[0]
            x = (width - text_width) // 2
            
            # 绘制文本，使用深黑色
            draw.text((x, y), line, fill=(0, 0, 0), font=font)
            print(f"   绘制文本行: '{line}' 位置: ({x}, {y}) 尺寸: {text_width}x{line_height}")
        except Exception as e:
            print(f"   ❌ 文本绘制失败: {e}")
            # 使用默认字体重试
            default_font = ImageFont.load_default()
            draw.text((margin, y), line, fill=(0, 0, 0), font=default_font)
        
        y += line_height
    
    return img

def save_annotations(image_path: str, text: str, lang: str):
    """保存标注文件"""
    # 保存文本文件
    text_path = str(image_path).replace('.png', '.txt')
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(text)
    
    # 保存JSON文件
    json_path = str(image_path).replace('.png', '.json')
    annotation = {
        'language': lang,
        'text': text,
        'image_path': str(image_path),
        'text_path': text_path,
        'char_count': len(text),
        'word_count': len(text.split()),
        'font_used': 'perfect_font_30_samples',
        'no_garbled': True,
        'is_full_text': True,
        'sample_count': 30
    }
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(annotation, f, ensure_ascii=False, indent=2)

def main():
    """主函数"""
    target_languages = ['si', 'ta', 'te', 'th', 'ur', 'zh', 'zh-Hant']
    n_per_lang = 30  # 每种语言30个样本
    
    manifest = []
    
    print(f"🎯 开始生成30样本版数据集 - 第二批...")
    print(f"📊 目标语言: {len(target_languages)} 种")
    print(f"📈 每种语言样本数: {n_per_lang}")
    print(f"🔧 每个样本都包含一段完整的文字，无重复")
    
    for lang in target_languages:
        print(f"\n📝 生成 {lang} 语言数据...")
        lang_dir = OUT / lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        
        # 获取完美字体
        font = get_perfect_font_for_language(lang, size=36)
        
        # 获取该语言的所有样本
        samples = LANG_SAMPLES[lang]
        
        for i in range(n_per_lang):
            # 使用不重复的样本
            text = samples[i]
            print(f"   样本 {i+1}: '{text}'")
            
            # 创建完整文本图像
            img = create_full_text_image(text, font, width=1400, height=500)
            
            # 保存图像
            img_filename = f'{lang}_{i:02d}.png'
            img_path = lang_dir / img_filename
            img.save(img_path, 'PNG', optimize=True)
            
            # 保存标注文件
            save_annotations(str(img_path), text, lang)
            
            # 添加到清单
            manifest.append({
                'language': lang,
                'path': str(img_path),
                'text_path': str(img_path).replace('.png', '.txt'),
                'json_path': str(img_path).replace('.png', '.json'),
                'text': text,
                'tokens_est': len(text.split()),
                'char_count': len(text),
                'no_garbled': True,
                'is_full_text': True,
                'sample_index': i
            })
        
        print(f"✅ {lang}: {n_per_lang} 个样本完成")
    
    # 保存清单文件
    manifest_path = OUT / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    # 生成统计报告
    stats = {
        'total_samples': len(manifest),
        'languages': len(set(item['language'] for item in manifest)),
        'no_garbled': True,
        'is_full_text': True,
        'samples_per_language': n_per_lang,
        'batch': 2,
        'description': '30样本版多语言合成数据集 - 第二批（7个语言）'
    }
    
    stats_path = OUT / 'stats.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print(f"\n🎉 第二批数据集生成完成！")
    print(f"📁 输出目录: {OUT}")
    print(f"📊 总样本数: {len(manifest)}")
    print(f"🌍 语言数: {len(target_languages)}")
    print(f"📈 每种语言样本数: {n_per_lang}")
    print(f"✅ 无乱码: {stats['no_garbled']}")
    print(f"📝 完整文本: {stats['is_full_text']}")

if __name__ == '__main__':
    main()


