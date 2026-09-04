#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整数据集OCR API测试脚本
"""

import sys
import time
sys.path.append('.')

from test_ocr_api import OCRAPITester

def main():
    # 创建测试器
    tester = OCRAPITester()

    print('🚀 开始完整数据集OCR API测试')
    print('='*70)

    # 运行完整测试
    start_time = time.time()
    tester.test_dataset(
        '/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended', 
        max_workers=4, 
        sample_size=None  # 测试所有样本
    )

    # 生成报告
    report = tester.generate_report()
    tester.save_report(report, 'full_dataset_test_report.json')

    # 打印报告
    tester.print_summary(report)

    # 详细分析
    print('\n' + '='*70)
    print('🌏 各语言详细测试结果')
    print('='*70)

    successful_langs = []
    failed_langs = []

    for lang in sorted(report['language_stats'].keys()):
        stats = report['language_stats'][lang]
        success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
        
        status = '✅' if success_rate > 0 else '❌'
        print(f'\n{status} {lang.upper()}:')
        print(f'   样本数: {stats["total"]}')
        print(f'   成功数: {stats["success"]}')  
        print(f'   成功率: {success_rate:.2%}')
        print(f'   准确率: {stats["avg_accuracy"]:.2%}')
        print(f'   响应时间: {stats["avg_response_time"]:.3f}秒')
        
        if success_rate > 0:
            successful_langs.append(lang)
        else:
            failed_langs.append(lang)

    total_time = time.time() - start_time
    
    print(f'\n{'='*70}')
    print(f'📊 测试总结')
    print(f'{'='*70}')
    print(f'✅ 支持的语言: {len(successful_langs)}种 - {", ".join(successful_langs)}')
    print(f'❌ 不支持的语言: {len(failed_langs)}种 - {", ".join(failed_langs)}')
    print(f'⏱️  总测试时间: {total_time:.2f}秒')
    print(f'📄 完整报告已保存: full_dataset_test_report.json')
    print(f'{'='*70}')

if __name__ == '__main__':
    main()


