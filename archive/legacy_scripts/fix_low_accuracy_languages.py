#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复低准确率语言数据集 - 蒙古语、印地语、尼泊尔语
使用正确的字体重新生成高质量图片
"""

import os
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess

# 安装必要的字体
def install_fonts():
    """安装必要的字体"""
    print("📦 安装字体...")
    fonts_to_install = [
        'fonts-noto-core',
        'fonts-noto-extra',
        'fonts-noto-cjk',
        'fonts-noto-mono'
    ]
    
    for font in fonts_to_install:
        try:
            subprocess.run(['apt-get', 'install', '-y', font], 
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except:
            pass
    
    print("✅ 字体安装完成")

def get_font_for_language(lang_code: str, size: int = 80) -> ImageFont.ImageFont:
    """
    根据语言代码获取对应的字体
    """
    font_paths = {
        'mn': [
            '/usr/share/fonts/truetype/noto/NotoSansMongolian-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
        ],
        'hi': [
            '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        ],
        'ne': [
            '/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf',
            '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        ]
    }
    
    paths = font_paths.get(lang_code, ['/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'])
    
    for font_path in paths:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, size)
                print(f"  ✅ 使用字体: {font_path} (大小: {size}px)")
                return font
            except Exception as e:
                print(f"  ⚠️  加载字体失败 {font_path}: {e}")
                continue
    
    # 如果都失败，使用默认字体
    print(f"  ⚠️  使用默认字体")
    return ImageFont.load_default()

def create_text_image(text: str, lang_code: str, width: int = 1400, height: int = 500) -> Image.Image:
    """
    创建高质量的文本图片
    
    Args:
        text: 要渲染的文本
        lang_code: 语言代码
        width: 图片宽度
        height: 图片高度
    
    Returns:
        PIL Image对象
    """
    # 创建白色背景
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 根据语言选择合适的字体大小
    font_sizes = {
        'mn': 80,  # 蒙古语
        'hi': 85,  # 印地语 - 稍大一点
        'ne': 85   # 尼泊尔语 - 稍大一点
    }
    
    font_size = font_sizes.get(lang_code, 80)
    font = get_font_for_language(lang_code, font_size)
    
    # 计算文本位置 (居中)
    # 使用textbbox获取文本边界框
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    # 如果文本太宽，自动换行
    if text_width > width - 100:
        # 简单换行：按空格或标点分割
        words = text.replace('।', '। ').replace('?', '? ').replace('.', '. ').split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if bbox[2] - bbox[0] > width - 100:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
                    current_line = []
            else:
                current_line.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        # 绘制多行文本
        y_offset = (height - len(lines) * (font_size + 20)) // 2
        
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            line_width = bbox[2] - bbox[0]
            x = (width - line_width) // 2
            draw.text((x, y_offset), line, fill='black', font=font)
            y_offset += font_size + 20
    else:
        # 单行居中绘制
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        draw.text((x, y), text, fill='black', font=font)
    
    return img

def regenerate_language_dataset(lang_code: str, lang_name: str, output_dir: Path):
    """
    重新生成指定语言的数据集
    
    Args:
        lang_code: 语言代码
        lang_name: 语言名称
        output_dir: 输出目录
    """
    print(f"\n{'='*70}")
    print(f"🔄 重新生成 {lang_name}({lang_code.upper()}) 数据集")
    print(f"{'='*70}")
    
    lang_dir = output_dir / lang_code
    
    if not lang_dir.exists():
        print(f"❌ 目录不存在: {lang_dir}")
        return
    
    # 读取现有的txt文件
    txt_files = sorted(lang_dir.glob('*.txt'))
    
    if not txt_files:
        print(f"❌ 没有找到txt文件")
        return
    
    print(f"📊 找到 {len(txt_files)} 个样本")
    
    # 为每个样本重新生成图片
    success_count = 0
    
    for txt_file in txt_files:
        # 读取文本
        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        if not text:
            print(f"  ⚠️  跳过空文本: {txt_file.name}")
            continue
        
        # 生成图片
        try:
            img = create_text_image(text, lang_code)
            
            # 保存图片
            img_file = txt_file.with_suffix('.png')
            img.save(img_file, 'PNG')
            
            # 更新JSON文件
            json_file = txt_file.with_suffix('.json')
            if json_file.exists():
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # 更新元数据
                metadata['regenerated'] = True
                metadata['regeneration_date'] = '2025-10-23'
                metadata['font_optimized'] = True
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            success_count += 1
            
            if success_count % 5 == 0:
                print(f"  ✅ 已处理: {success_count}/{len(txt_files)}")
        
        except Exception as e:
            print(f"  ❌ 处理失败 {txt_file.name}: {e}")
    
    print(f"✅ {lang_name} 数据集重新生成完成: {success_count}/{len(txt_files)} 个样本")

def main():
    """主函数"""
    print("🔧 修复低准确率语言数据集")
    print("="*70)
    
    # 安装字体
    install_fonts()
    
    # 输出目录
    output_dir = Path('/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended')
    
    if not output_dir.exists():
        print(f"❌ 数据集目录不存在: {output_dir}")
        return
    
    # 重新生成三种语言
    languages = [
        ('mn', '蒙古语'),
        ('hi', '印地语'),
        ('ne', '尼泊尔语')
    ]
    
    for lang_code, lang_name in languages:
        regenerate_language_dataset(lang_code, lang_name, output_dir)
    
    print("\n" + "="*70)
    print("🎉 所有语言数据集重新生成完成！")
    print("="*70)
    print("\n💡 下一步:")
    print("  1. 检查生成的图片质量")
    print("  2. 重新运行OCR API测试")
    print("  3. 验证准确率是否提升")

if __name__ == "__main__":
    main()


