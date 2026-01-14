#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR API 测试脚本 - 使用tqdm显示进度
"""

import sys
import time
import json
import requests
from pathlib import Path
from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from datetime import datetime

class OCRAPITester:
    def __init__(self, api_url: str = "http://localhost:16110", api_key: str = "***REMOVED-ROTATE-THIS-KEY***"):
        self.api_url = api_url
        self.api_key = api_key
        self.results = []
        self.performance_stats = []

    def calculate_accuracy(self, ground_truth: str, predicted: str) -> float:
        """计算字符级准确率"""
        if not ground_truth or not predicted:
            return 0.0
        
        # 简单的字符匹配准确率
        matches = sum(1 for a, b in zip(ground_truth, predicted) if a == b)
        max_len = max(len(ground_truth), len(predicted))
        
        if max_len == 0:
            return 0.0
            
        return (matches / max_len) * 100

    def test_single_image(self, image_path: str, ground_truth: str, language: str) -> Dict:
        """测试单张图片"""
        start_time = time.time()

        try:
            # 准备请求
            with open(image_path, 'rb') as f:
                files = {'file': f}
                data = {'language': language}
                headers = {'Authorization': f'Bearer {self.api_key}'}

                # 发送请求
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
                
                # 正确提取识别文本
                predicted_text = ''
                if result.get('data') and len(result['data']) > 0:
                    # 合并所有识别到的文本
                    predicted_text = ' '.join([item.get('text', '') for item in result['data']])
                
                # 计算准确率
                accuracy = self.calculate_accuracy(ground_truth, predicted_text)

                return {
                    'image_path': image_path,
                    'language': language,
                    'ground_truth': ground_truth,
                    'predicted_text': predicted_text,
                    'accuracy': accuracy,
                    'response_time': response_time,
                    'status': 'success',
                    'confidence': 1.0,
                    'error_message': ''
                }
            else:
                return {
                    'image_path': image_path,
                    'language': language,
                    'ground_truth': ground_truth,
                    'predicted_text': '',
                    'accuracy': 0.0,
                    'response_time': response_time,
                    'status': f'error_{response.status_code}',
                    'confidence': 0.0,
                    'error_message': response.text[:200]
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
                'response_time': response_time,
                'status': f'exception',
                'confidence': 0.0,
                'error_message': str(e)[:200]
            }

    def load_dataset(self, dataset_path: str, sample_size: int = None) -> List[Dict]:
        """加载数据集"""
        dataset = []
        dataset_dir = Path(dataset_path)
        
        for lang_dir in sorted(dataset_dir.iterdir()):
            if not lang_dir.is_dir():
                continue
            
            lang_code = lang_dir.name
            samples = []
            
            # 读取该语言的所有样本
            for img_file in sorted(lang_dir.glob('*.png')):
                txt_file = img_file.with_suffix('.txt')
                
                if txt_file.exists():
                    with open(txt_file, 'r', encoding='utf-8') as f:
                        ground_truth = f.read().strip()
                    
                    samples.append({
                        'image_path': str(img_file),
                        'ground_truth': ground_truth,
                        'language': lang_code
                    })
            
            # 如果指定了sample_size，则限制每种语言的样本数
            if sample_size and len(samples) > sample_size:
                samples = samples[:sample_size]
            
            dataset.extend(samples)
        
        return dataset

    def test_dataset(self, dataset_path: str, max_workers: int = 4, sample_size: int = None):
        """测试整个数据集"""
        # 加载数据集
        print(f"🔍 加载数据集: {dataset_path}")
        dataset = self.load_dataset(dataset_path, sample_size)
        
        if not dataset:
            print("❌ 数据集为空！")
            return
        
        # 统计信息
        languages = set(item['language'] for item in dataset)
        print(f"📊 总样本数: {len(dataset)}")
        print(f"🌏 语言数量: {len(languages)}")
        print(f"🔄 并发数: {max_workers}")
        print()
        
        # 使用ThreadPoolExecutor和tqdm进行并发测试
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            future_to_sample = {
                executor.submit(
                    self.test_single_image,
                    sample['image_path'],
                    sample['ground_truth'],
                    sample['language']
                ): sample for sample in dataset
            }
            
            # 使用tqdm显示进度
            with tqdm(total=len(dataset), desc="🚀 测试进度", unit="样本", 
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]',
                     ncols=100, colour='green') as pbar:
                
                for future in as_completed(future_to_sample):
                    result = future.result()
                    self.results.append(result)
                    
                    # 更新进度条描述
                    success_count = sum(1 for r in self.results if r['status'] == 'success')
                    success_rate = (success_count / len(self.results)) * 100
                    pbar.set_postfix({
                        '成功': f'{success_count}/{len(self.results)}',
                        '成功率': f'{success_rate:.1f}%'
                    })
                    pbar.update(1)
        
        total_time = time.time() - start_time
        
        print(f"\n⏱️  总测试时间: {total_time:.2f}秒")
        print(f"📈 平均每张图片: {total_time/len(dataset):.2f}秒")

    def generate_report(self) -> Dict:
        """生成测试报告"""
        if not self.results:
            return {}
        
        # 计算总体统计
        total_samples = len(self.results)
        successful_samples = sum(1 for r in self.results if r['status'] == 'success')
        failed_samples = total_samples - successful_samples
        
        # 计算准确率（只计算成功的样本）
        successful_results = [r for r in self.results if r['status'] == 'success']
        avg_accuracy = sum(r['accuracy'] for r in successful_results) / len(successful_results) if successful_results else 0
        
        # 性能统计
        response_times = [r['response_time'] for r in self.results]
        
        # 按语言统计
        language_stats = {}
        for result in self.results:
            lang = result['language']
            if lang not in language_stats:
                language_stats[lang] = {
                    'total': 0,
                    'success': 0,
                    'total_accuracy': 0,
                    'total_response_time': 0
                }
            
            language_stats[lang]['total'] += 1
            language_stats[lang]['total_response_time'] += result['response_time']
            
            if result['status'] == 'success':
                language_stats[lang]['success'] += 1
                language_stats[lang]['total_accuracy'] += result['accuracy']
        
        # 计算平均值
        for lang in language_stats:
            stats = language_stats[lang]
            stats['avg_response_time'] = stats['total_response_time'] / stats['total']
            stats['avg_accuracy'] = stats['total_accuracy'] / stats['success'] if stats['success'] > 0 else 0
        
        return {
            'api_url': self.api_url,
            'timestamp': datetime.now().isoformat(),
            'total_samples': total_samples,
            'successful_samples': successful_samples,
            'failed_samples': failed_samples,
            'success_rate': successful_samples / total_samples if total_samples > 0 else 0,
            'avg_accuracy': avg_accuracy,
            'performance': {
                'avg_response_time': sum(response_times) / len(response_times),
                'min_response_time': min(response_times),
                'max_response_time': max(response_times),
                'total_time': sum(response_times)
            },
            'language_stats': language_stats,
            'detailed_results': self.results
        }

    def save_report(self, report: Dict, filename: str = 'ocr_test_report.json'):
        """保存测试报告"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📄 测试报告已保存: {filename}")

    def print_summary(self, report: Dict):
        """打印测试摘要"""
        print("\n" + "="*70)
        print("📊 OCR API 测试报告")
        print("="*70)
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
        
        print(f"\n🌏 按语言统计:")
        for lang, stats in sorted(report['language_stats'].items()):
            success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
            print(f"   {lang}: 成功率 {success_rate:.2%}, 准确率 {stats['avg_accuracy']:.2%}, 平均响应 {stats['avg_response_time']:.2f}秒")


def main():
    """主函数"""
    print("🔧 OCR API 测试工具 (带进度条)")
    print("="*70)
    
    # 创建测试器
    tester = OCRAPITester()
    
    # 运行测试
    dataset_path = '/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended'
    tester.test_dataset(dataset_path, max_workers=4, sample_size=None)
    
    # 生成报告
    report = tester.generate_report()
    
    # 保存报告
    tester.save_report(report, 'tqdm_ocr_test_report.json')
    
    # 打印摘要
    tester.print_summary(report)


if __name__ == "__main__":
    main()


