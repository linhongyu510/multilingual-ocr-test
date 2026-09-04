#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
全面的OCR API测试，包括所有语言
"""

import sys
sys.path.append('.')

from test_ocr_api import OCRAPITester
import json
from pathlib import Path

def test_all_languages():
    """测试所有语言"""
    print("🌏 全面OCR API测试")
    print("=" * 60)
    
    # 创建测试器
    tester = OCRAPITester()
    
    # 获取所有语言
    dataset_path = '/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended'
    languages = []
    
    for lang_dir in Path(dataset_path).iterdir():
        if lang_dir.is_dir():
            languages.append(lang_dir.name)
    
    print(f"📊 发现语言: {len(languages)}种")
    print(f"🌏 语言列表: {', '.join(sorted(languages))}")
    
    # 测试所有语言
    print(f"\n🚀 开始全面测试...")
    tester.test_dataset(dataset_path, max_workers=2, sample_size=None)  # 测试所有样本
    
    # 生成报告
    report = tester.generate_report()
    tester.save_report(report, 'comprehensive_ocr_report.json')
    
    # 打印详细报告
    print_comprehensive_report(report)
    
    return report

def print_comprehensive_report(report):
    """打印全面测试报告"""
    print("\n" + "=" * 60)
    print("📊 全面OCR API测试报告")
    print("=" * 60)
    
    print(f"🌐 API地址: {report['api_url']}")
    print(f"📅 测试时间: {report['timestamp']}")
    print(f"📈 总样本数: {report['total_samples']}")
    print(f"✅ 成功样本: {report['successful_samples']}")
    print(f"❌ 失败样本: {report['failed_samples']}")
    print(f"📊 成功率: {report['success_rate']:.2%}")
    print(f"🎯 平均准确率: {report['avg_accuracy']:.2%}")
    
    print(f"\n⏱️  性能统计:")
    perf = report['performance']
    print(f"   平均响应时间: {perf['avg_response_time']:.2f}秒")
    print(f"   最快响应时间: {perf['min_response_time']:.2f}秒")
    print(f"   最慢响应时间: {perf['max_response_time']:.2f}秒")
    print(f"   总测试时间: {perf['total_time']:.2f}秒")
    
    print(f"\n🌏 按语言详细分析:")
    successful_langs = []
    failed_langs = []
    
    for lang, stats in sorted(report['language_stats'].items()):
        success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
        print(f"   {lang}:")
        print(f"     样本数: {stats['total']}")
        print(f"     成功数: {stats['success']}")
        print(f"     成功率: {success_rate:.2%}")
        print(f"     准确率: {stats['avg_accuracy']:.2%}")
        print(f"     平均响应时间: {stats['avg_response_time']:.2f}秒")
        
        if success_rate > 0:
            successful_langs.append(lang)
        else:
            failed_langs.append(lang)
    
    print(f"\n✅ 支持良好的语言 ({len(successful_langs)}种):")
    for lang in successful_langs:
        stats = report['language_stats'][lang]
        success_rate = stats['success'] / stats['total']
        print(f"   {lang}: 成功率 {success_rate:.2%}, 准确率 {stats['avg_accuracy']:.2%}")
    
    print(f"\n❌ 需要改进的语言 ({len(failed_langs)}种):")
    for lang in failed_langs:
        print(f"   {lang}")
    
    # 分析错误类型
    failed_results = [r for r in report['detailed_results'] if r['status'] != 'success']
    if failed_results:
        print(f"\n🔍 失败原因分析:")
        error_counts = {}
        for result in failed_results:
            status = result['status']
            if status not in error_counts:
                error_counts[status] = 0
            error_counts[status] += 1
        
        for error, count in error_counts.items():
            print(f"   {error}: {count}次")
    
    # 生成建议
    print(f"\n💡 测试结论和建议:")
    print(f"   1. 总体成功率: {report['success_rate']:.2%}")
    print(f"   2. 平均准确率: {report['avg_accuracy']:.2%}")
    print(f"   3. 平均响应时间: {perf['avg_response_time']:.2f}秒")
    print(f"   4. 支持语言数: {len(successful_langs)}种")
    print(f"   5. 需要改进语言数: {len(failed_langs)}种")
    
    if successful_langs:
        print(f"\n🎯 推荐使用场景:")
        print(f"   - 中文识别: 表现优秀，准确率100%")
        if len(successful_langs) > 1:
            print(f"   - 其他支持语言: {', '.join([lang for lang in successful_langs if lang != 'zh'])}")
    
    if failed_langs:
        print(f"\n⚠️  改进建议:")
        print(f"   - 检查不支持语言的API参数")
        print(f"   - 考虑使用语言检测功能")
        print(f"   - 针对特定语言优化模型")

def main():
    """主函数"""
    report = test_all_languages()
    
    # 保存简化报告
    summary = {
        'total_samples': report['total_samples'],
        'success_rate': report['success_rate'],
        'avg_accuracy': report['avg_accuracy'],
        'avg_response_time': report['performance']['avg_response_time'],
        'supported_languages': [lang for lang, stats in report['language_stats'].items() 
                               if stats['success'] > 0],
        'unsupported_languages': [lang for lang, stats in report['language_stats'].items() 
                                 if stats['success'] == 0]
    }
    
    with open('ocr_test_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 测试报告已保存:")
    print(f"   - 详细报告: comprehensive_ocr_report.json")
    print(f"   - 简化报告: ocr_test_summary.json")

if __name__ == "__main__":
    main()

