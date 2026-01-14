#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR API 详细指标测试 - 包括准确率、词错率(WER)、字符错率(CER)
"""

import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime
import Levenshtein

class DetailedOCRTester:
    def __init__(self, api_url: str = "http://localhost:16110", api_key: str = "***REMOVED-ROTATE-THIS-KEY***"):
        self.api_url = api_url
        self.api_key = api_key
        self.results = []

    def calculate_cer(self, reference: str, hypothesis: str) -> float:
        """
        计算字符错误率 (Character Error Rate)
        CER = (S + D + I) / N
        S: 替换, D: 删除, I: 插入, N: 参考文本长度
        """
        if not reference:
            return 0.0 if not hypothesis else 100.0
        
        distance = Levenshtein.distance(reference, hypothesis)
        cer = (distance / len(reference)) * 100
        return min(cer, 100.0)  # 限制最大100%

    def calculate_wer(self, reference: str, hypothesis: str) -> float:
        """
        计算词错误率 (Word Error Rate)
        WER = (S + D + I) / N
        S: 替换, D: 删除, I: 插入, N: 参考词数
        """
        ref_words = reference.split()
        hyp_words = hypothesis.split()
        
        if not ref_words:
            return 0.0 if not hyp_words else 100.0
        
        distance = Levenshtein.distance(' '.join(ref_words), ' '.join(hyp_words))
        wer = (distance / len(' '.join(ref_words))) * 100
        return min(wer, 100.0)  # 限制最大100%

    def calculate_accuracy(self, reference: str, hypothesis: str) -> float:
        """
        计算准确率
        Accuracy = (1 - CER/100) * 100
        """
        cer = self.calculate_cer(reference, hypothesis)
        accuracy = 100 - cer
        return max(accuracy, 0.0)

    def test_single_image(self, image_path: str, ground_truth: str, language: str) -> Dict:
        """测试单张图片"""
        start_time = time.time()

        try:
            with open(image_path, 'rb') as f:
                files = {'file': f}
                data = {'language': language}
                headers = {'Authorization': f'Bearer {self.api_key}'}

                response = requests.post(
                    f"{self.api_url}/v1/ocr", 
                    files=files, 
                    data=data, 
                    headers=headers, 
                    timeout=30
                )

            end_time = time.time()
            response_time = end_time - start_time

            if response.status_code == 200:
                result = response.json()
                
                # 提取识别文本
                predicted_text = ''
                if result.get('data') and len(result['data']) > 0:
                    predicted_text = ' '.join([item.get('text', '') for item in result['data']])
                
                # 计算各种指标
                accuracy = self.calculate_accuracy(ground_truth, predicted_text)
                cer = self.calculate_cer(ground_truth, predicted_text)
                wer = self.calculate_wer(ground_truth, predicted_text)

                return {
                    'image_path': image_path,
                    'language': language,
                    'ground_truth': ground_truth,
                    'predicted_text': predicted_text,
                    'accuracy': accuracy,
                    'cer': cer,
                    'wer': wer,
                    'response_time': response_time,
                    'status': 'success'
                }
            else:
                return {
                    'image_path': image_path,
                    'language': language,
                    'ground_truth': ground_truth,
                    'predicted_text': '',
                    'accuracy': 0.0,
                    'cer': 100.0,
                    'wer': 100.0,
                    'response_time': response_time,
                    'status': f'error_{response.status_code}'
                }

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time

            return {
                'image_path': image_path,
                'language': language,
                'ground_truth': ground_truth,
                'predicted_text': '',
                'accuracy': 0.0,
                'cer': 100.0,
                'wer': 100.0,
                'response_time': response_time,
                'status': 'exception'
            }

    def load_dataset(self, dataset_path: str) -> List[Dict]:
        """加载数据集"""
        dataset = []
        dataset_dir = Path(dataset_path)
        
        for lang_dir in sorted(dataset_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            
            lang_code = lang_dir.name
            
            for img_file in sorted(lang_dir.glob('*.png')):
                txt_file = img_file.with_suffix('.txt')
                
                if txt_file.exists():
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        ground_truth = f.read().strip()
                    
                    dataset.append({
                        'image_path': str(img_file),
                        'ground_truth': ground_truth,
                        'language': lang_code
                    })
        
        return dataset

    def test_dataset(self, dataset_path: str, max_workers: int = 4):
        """测试整个数据集"""
        print(f"🔍 加载数据集: {dataset_path}")
        dataset = self.load_dataset(dataset_path)
        
        if not dataset:
            print("❌ 数据集为空！")
            return
        
        languages = set(item['language'] for item in dataset)
        print(f"📊 总样本数: {len(dataset)}")
        print(f"🌏 语言数量: {len(languages)}")
        print()
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sample = {
                executor.submit(
                    self.test_single_image,
                    sample['image_path'],
                    sample['ground_truth'],
                    sample['language']
                ): sample for sample in dataset
            }
            
            with tqdm(total=len(dataset), desc="🚀 测试进度", unit="样本", ncols=100, colour='green') as pbar:
                for future in as_completed(future_to_sample):
                    result = future.result()
                    self.results.append(result)
                    
                    success_count = sum(1 for r in self.results if r['status'] == 'success')
                    pbar.set_postfix({'成功': f'{success_count}/{len(self.results)}'})
                    pbar.update(1)
        
        total_time = time.time() - start_time
        print(f"\n⏱️  总测试时间: {total_time:.2f}秒 ({total_time/60:.1f}分钟)")

    def generate_language_report(self) -> Dict:
        """生成按语言统计的报告"""
        language_stats = {}
        
        for result in self.results:
            lang = result['language']
            if lang not in language_stats:
                language_stats[lang] = {
                    'total': 0,
                    'success': 0,
                    'total_accuracy': 0,
                    'total_cer': 0,
                    'total_wer': 0,
                    'total_response_time': 0,
                    'success_results': []
                }
            
            language_stats[lang]['total'] += 1
            language_stats[lang]['total_response_time'] += result['response_time']
            
            if result['status'] == 'success':
                language_stats[lang]['success'] += 1
                language_stats[lang]['total_accuracy'] += result['accuracy']
                language_stats[lang]['total_cer'] += result['cer']
                language_stats[lang]['total_wer'] += result['wer']
                language_stats[lang]['success_results'].append(result)
        
        # 计算平均值
        for lang in language_stats:
            stats = language_stats[lang]
            stats['success_rate'] = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
            stats['avg_response_time'] = stats['total_response_time'] / stats['total']
            
            if stats['success'] > 0:
                stats['avg_accuracy'] = stats['total_accuracy'] / stats['success']
                stats['avg_cer'] = stats['total_cer'] / stats['success']
                stats['avg_wer'] = stats['total_wer'] / stats['success']
            else:
                stats['avg_accuracy'] = 0
                stats['avg_cer'] = 100
                stats['avg_wer'] = 100
        
        return language_stats

    def print_table_report(self, language_stats: Dict):
        """打印表格格式的报告"""
        print("\n" + "="*120)
        print("📊 OCR API 详细指标测试报告")
        print("="*120)
        
        # 表头
        header = f"{'语言':<12} {'样本数':<8} {'成功率':<10} {'准确率':<10} {'字符错率':<12} {'词错率':<10} {'平均响应时间':<12} {'状态':<10}"
        print(header)
        print("-"*120)
        
        # 按语言排序输出
        for lang in sorted(language_stats.keys()):
            stats = language_stats[lang]
            
            # 确定状态
            if stats['success_rate'] == 0:
                status = "❌ 不支持"
            elif stats['avg_accuracy'] >= 90:
                status = "⭐ 优秀"
            elif stats['avg_accuracy'] >= 70:
                status = "✅ 良好"
            elif stats['avg_accuracy'] >= 50:
                status = "📊 一般"
            else:
                status = "⚠️  需改进"
            
            row = (
                f"{lang.upper():<12} "
                f"{stats['total']:<8} "
                f"{stats['success_rate']:>8.1f}% "
                f"{stats['avg_accuracy']:>8.2f}% "
                f"{stats['avg_cer']:>10.2f}% "
                f"{stats['avg_wer']:>8.2f}% "
                f"{stats['avg_response_time']:>10.3f}秒 "
                f"{status:<10}"
            )
            print(row)
        
        print("="*120)

    def save_report(self, language_stats: Dict, filename: str = 'detailed_metrics_report.json'):
        """保存报告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_samples': len(self.results),
            'successful_samples': sum(1 for r in self.results if r['status'] == 'success'),
            'language_stats': {
                lang: {
                    'total': stats['total'],
                    'success': stats['success'],
                    'success_rate': stats['success_rate'],
                    'avg_accuracy': stats['avg_accuracy'],
                    'avg_cer': stats['avg_cer'],
                    'avg_wer': stats['avg_wer'],
                    'avg_response_time': stats['avg_response_time']
                }
                for lang, stats in language_stats.items()
            },
            'detailed_results': self.results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 详细报告已保存: {filename}")

    def generate_summary(self, language_stats: Dict):
        """生成汇总统计"""
        print("\n" + "="*120)
        print("📈 汇总统计")
        print("="*120)
        
        total_samples = sum(stats['total'] for stats in language_stats.values())
        total_success = sum(stats['success'] for stats in language_stats.values())
        
        successful_langs = [lang for lang, stats in language_stats.items() if stats['success_rate'] > 0]
        failed_langs = [lang for lang, stats in language_stats.items() if stats['success_rate'] == 0]
        
        # 计算加权平均（只计算成功的样本）
        total_accuracy = sum(stats['total_accuracy'] for stats in language_stats.values())
        total_cer = sum(stats['total_cer'] for stats in language_stats.values())
        total_wer = sum(stats['total_wer'] for stats in language_stats.values())
        
        avg_accuracy = total_accuracy / total_success if total_success > 0 else 0
        avg_cer = total_cer / total_success if total_success > 0 else 100
        avg_wer = total_wer / total_success if total_success > 0 else 100
        
        print(f"\n总体指标:")
        print(f"  总样本数:     {total_samples}")
        print(f"  成功样本:     {total_success}")
        print(f"  失败样本:     {total_samples - total_success}")
        print(f"  总成功率:     {(total_success/total_samples*100):.2f}%")
        print(f"  平均准确率:   {avg_accuracy:.2f}%")
        print(f"  平均CER:      {avg_cer:.2f}%")
        print(f"  平均WER:      {avg_wer:.2f}%")
        
        print(f"\n语言支持:")
        print(f"  ✅ 支持的语言: {len(successful_langs)}种")
        print(f"  ❌ 不支持:     {len(failed_langs)}种")
        
        # Top 10 最佳语言
        print(f"\n🏆 Top 10 最佳语言 (按准确率):")
        top_langs = sorted(
            [(lang, stats) for lang, stats in language_stats.items() if stats['success_rate'] > 0],
            key=lambda x: x[1]['avg_accuracy'],
            reverse=True
        )[:10]
        
        for i, (lang, stats) in enumerate(top_langs, 1):
            print(f"  {i:2}. {lang.upper():<10} 准确率 {stats['avg_accuracy']:6.2f}%  CER {stats['avg_cer']:6.2f}%  响应 {stats['avg_response_time']:.3f}秒")
        
        # 最需要改进的语言
        print(f"\n⚠️  最需要改进的语言 (成功但准确率<50%):")
        low_acc_langs = sorted(
            [(lang, stats) for lang, stats in language_stats.items() if stats['success_rate'] > 0 and stats['avg_accuracy'] < 50],
            key=lambda x: x[1]['avg_accuracy']
        )
        
        for lang, stats in low_acc_langs:
            print(f"  • {lang.upper():<10} 准确率 {stats['avg_accuracy']:6.2f}%  CER {stats['avg_cer']:6.2f}%")


def main():
    print("🔧 OCR API 详细指标测试工具")
    print("="*120)
    
    # 创建测试器
    tester = DetailedOCRTester()
    
    # 运行测试
    dataset_path = '/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended'
    tester.test_dataset(dataset_path, max_workers=4)
    
    # 生成报告
    language_stats = tester.generate_language_report()
    
    # 打印表格
    tester.print_table_report(language_stats)
    
    # 生成汇总
    tester.generate_summary(language_stats)
    
    # 保存报告
    tester.save_report(language_stats, 'detailed_metrics_report.json')
    
    print("\n" + "="*120)
    print("✅ 测试完成！")
    print("="*120)


if __name__ == "__main__":
    main()


