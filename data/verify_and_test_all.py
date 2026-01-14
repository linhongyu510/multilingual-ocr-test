#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证模型映射并重新测试所有语言
"""

import sys
sys.path.append('.')

from test_ocr_detailed_metrics import DetailedOCRTester

# 根据PaddleOCR官方文档的正确映射
CORRECT_LANGUAGE_MODEL_MAPPING = {
    # 数据集语言代码 -> (应使用的模型, PaddleOCR语言代码)
    'zh': ('PP-OCRv5_server_rec', 'ch'),
    'zh-hant': ('PP-OCRv5_server_rec', 'chinese_cht'),
    'ja': ('PP-OCRv5_server_rec', 'japan'),
    'ko': ('korean_PP-OCRv5_mobile_rec', 'korean'),
    'id': ('latin_PP-OCRv5_mobile_rec', 'latin'),
    'ms': ('latin_PP-OCRv5_mobile_rec', 'latin'),
    'tl': ('latin_PP-OCRv5_mobile_rec', 'latin'),
    'vi': ('latin_PP-OCRv5_mobile_rec', 'latin'),
    'th': ('th_PP-OCRv5_mobile_rec', 'th'),
    'ta': ('ta_PP-OCRv5_mobile_rec', 'ta'),
    'te': ('te_PP-OCRv5_mobile_rec', 'te'),
    'hi': ('devanagari_PP-OCRv5_mobile_rec', 'devanagari'),
    'ne': ('devanagari_PP-OCRv5_mobile_rec', 'devanagari'),
    'mr': ('devanagari_PP-OCRv5_mobile_rec', 'devanagari'),
    'ur': ('arabic_PP-OCRv5_mobile_rec', 'arabic'),
    'ug': ('arabic_PP-OCRv5_mobile_rec', 'arabic'),
    'ar': ('arabic_PP-OCRv5_mobile_rec', 'arabic'),
    'fa': ('arabic_PP-OCRv5_mobile_rec', 'arabic'),
    'mn': ('cyrillic_PP-OCRv5_mobile_rec', 'cyrillic'),
    'ru': ('eslav_PP-OCRv5_mobile_rec', 'ru'),
    'uk': ('eslav_PP-OCRv5_mobile_rec', 'uk'),
    'be': ('eslav_PP-OCRv5_mobile_rec', 'be'),
    'bg': ('cyrillic_PP-OCRv5_mobile_rec', 'cyrillic'),
    # 可能不支持的语言
    'bn': ('未知', 'bn'),
    'km': ('未知', 'km'),
    'kn': ('未知', 'kn'),
    'lo': ('未知', 'lo'),
    'ml': ('未知', 'ml'),
    'my': ('未知', 'my'),
    'si': ('未知', 'si')
}

def verify_model_mapping():
    """验证模型映射"""
    print("="*80)
    print("🔍 验证语言-模型映射")
    print("="*80)
    
    print(f"\n{'语言代码':<12} {'语言名称':<15} {'应使用的模型':<35} {'状态':<10}")
    print("-"*80)
    
    lang_names = {
        'zh': '简体中文', 'zh-hant': '繁体中文', 'ja': '日语', 'ko': '韩语',
        'id': '印尼语', 'ms': '马来语', 'tl': '菲律宾语', 'vi': '越南语',
        'th': '泰语', 'ta': '泰米尔语', 'te': '泰卢固语',
        'hi': '印地语', 'ne': '尼泊尔语', 'mr': '马拉地语',
        'ur': '乌尔都语', 'ug': '维吾尔语', 'ar': '阿拉伯语', 'fa': '波斯语',
        'mn': '蒙古语', 'ru': '俄语', 'uk': '乌克兰语', 'be': '白俄罗斯语', 'bg': '保加利亚语',
        'bn': '孟加拉语', 'km': '高棉语', 'kn': '卡纳达语', 'lo': '老挝语',
        'ml': '马拉雅拉姆语', 'my': '缅甸语', 'si': '僧伽罗语'
    }
    
    for lang_code, (model, paddle_lang) in sorted(CORRECT_LANGUAGE_MODEL_MAPPING.items()):
        lang_name = lang_names.get(lang_code, lang_code)
        status = '✅ 已配置' if model != '未知' else '❌ 不支持'
        print(f"{lang_code.upper():<12} {lang_name:<15} {model:<35} {status:<10}")
    
    print("="*80)

def main():
    """主函数"""
    print("🔧 完整OCR API测试 - 验证模型映射版本")
    print("="*80)
    
    # 验证映射
    verify_model_mapping()
    
    # 运行完整测试
    print("\n🚀 开始完整测试...")
    print("="*80)
    
    tester = DetailedOCRTester()
    dataset_path = '/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended'
    
    # 测试数据集
    tester.test_dataset(dataset_path, max_workers=4)
    
    # 生成报告
    language_stats = tester.generate_language_report()
    
    # 打印表格
    tester.print_table_report(language_stats)
    
    # 生成汇总
    tester.generate_summary(language_stats)
    
    # 保存报告
    tester.save_report(language_stats, 'final_verified_test_report.json')
    
    # 验证每种语言使用的模型
    print("\n" + "="*80)
    print("🔍 模型使用验证")
    print("="*80)
    
    for lang_code in sorted(language_stats.keys()):
        stats = language_stats[lang_code]
        expected = CORRECT_LANGUAGE_MODEL_MAPPING.get(lang_code.lower(), ('未知', '未知'))
        
        status_icon = '✅' if stats['success_rate'] > 0 else '❌'
        model_status = '✅' if expected[0] != '未知' else '❌'
        
        print(f"{status_icon} {lang_code.upper():<8} → {expected[0]:<35} 准确率: {stats['avg_accuracy']:>6.2f}% {model_status}")
    
    print("="*80)
    print("✅ 测试完成！")
    print("="*80)

if __name__ == "__main__":
    main()


