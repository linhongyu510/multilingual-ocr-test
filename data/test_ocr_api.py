#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
使用synthetic_30_samples_extended数据集测试OCR API的准确率和性能
"""

import requests
import json
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple
import concurrent.futures
from datetime import datetime

class OCRAPITester:
    def __init__(self, api_url: str = "http://localhost:16110", api_key: str = "***REMOVED-ROTATE-THIS-KEY***"):
        self.api_url = api_url
        self.api_key = api_key
        self.results = []
        self.performance_stats = []
        
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
                response = requests.post(f"{self.api_url}/v1/ocr", files=files, data=data, headers=headers, timeout=30)
                
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
                    'confidence': 1.0,  # API没有返回置信度，设为1.0
                    'error_message': '',
                    'api_response': result  # 保存完整API响应
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
                    'error_message': response.text
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
                'status': f'exception_{str(e)}',
                'confidence': 0.0,
                'error_message': str(e)
            }
    
    def calculate_accuracy(self, ground_truth: str, predicted: str) -> float:
        """计算准确率"""
        if not ground_truth or not predicted:
            return 0.0
        
        # 简单的字符级准确率
        gt_chars = set(ground_truth.lower().replace(' ', ''))
        pred_chars = set(predicted.lower().replace(' ', ''))
        
        if not gt_chars:
            return 0.0
        
        intersection = gt_chars.intersection(pred_chars)
        return len(intersection) / len(gt_chars)
    
    def load_dataset(self, dataset_path: str) -> List[Tuple[str, str, str]]:
        """加载数据集"""
        dataset = []
        dataset_dir = Path(dataset_path)
        
        for lang_dir in dataset_dir.iterdir():
            if lang_dir.is_dir():
                language = lang_dir.name
                
                # 获取该语言的所有图片
                for img_file in lang_dir.glob('*.png'):
                    txt_file = img_file.with_suffix('.txt')
                    
                    if txt_file.exists():
                        with open(txt_file, 'r', encoding='utf-8') as f:
                            ground_truth = f.read().strip()
                        
                        dataset.append((str(img_file), ground_truth, language))
        
        return dataset
    
    def test_dataset(self, dataset_path: str, max_workers: int = 4, sample_size: int = None):
        """测试整个数据集"""
        print(f"🔍 加载数据集: {dataset_path}")
        dataset = self.load_dataset(dataset_path)
        
        if sample_size:
            dataset = dataset[:sample_size]
        
        print(f"📊 测试样本数: {len(dataset)}")
        print(f"🌏 支持语言: {len(set(item[2] for item in dataset))}")
        
        # 并发测试
        print(f"🚀 开始测试 (并发数: {max_workers})...")
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for img_path, ground_truth, language in dataset:
                future = executor.submit(self.test_single_image, img_path, ground_truth, language)
                futures.append(future)
            
            # 收集结果
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()
                self.results.append(result)
                
                if (i + 1) % 10 == 0:
                    print(f"✅ 已完成: {i + 1}/{len(dataset)}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"⏱️  总测试时间: {total_time:.2f}秒")
        print(f"📈 平均每张图片: {total_time/len(dataset):.2f}秒")
    
    def generate_report(self) -> Dict:
        """生成测试报告"""
        if not self.results:
            return {}
        
        # 基本统计
        total_samples = len(self.results)
        successful_samples = len([r for r in self.results if r['status'] == 'success'])
        failed_samples = total_samples - successful_samples
        
        # 准确率统计
        accuracies = [r['accuracy'] for r in self.results if r['status'] == 'success']
        avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
        
        # 性能统计
        response_times = [r['response_time'] for r in self.results]
        avg_response_time = sum(response_times) / len(response_times)
        min_response_time = min(response_times)
        max_response_time = max(response_times)
        
        # 按语言统计
        language_stats = {}
        for result in self.results:
            lang = result['language']
            if lang not in language_stats:
                language_stats[lang] = {
                    'total': 0,
                    'success': 0,
                    'accuracies': [],
                    'response_times': []
                }
            
            language_stats[lang]['total'] += 1
            if result['status'] == 'success':
                language_stats[lang]['success'] += 1
                language_stats[lang]['accuracies'].append(result['accuracy'])
            language_stats[lang]['response_times'].append(result['response_time'])
        
        # 计算每种语言的平均准确率
        for lang in language_stats:
            if language_stats[lang]['accuracies']:
                language_stats[lang]['avg_accuracy'] = sum(language_stats[lang]['accuracies']) / len(language_stats[lang]['accuracies'])
            else:
                language_stats[lang]['avg_accuracy'] = 0.0
            
            language_stats[lang]['avg_response_time'] = sum(language_stats[lang]['response_times']) / len(language_stats[lang]['response_times'])
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'api_url': self.api_url,
            'total_samples': total_samples,
            'successful_samples': successful_samples,
            'failed_samples': failed_samples,
            'success_rate': successful_samples / total_samples if total_samples > 0 else 0.0,
            'avg_accuracy': avg_accuracy,
            'performance': {
                'avg_response_time': avg_response_time,
                'min_response_time': min_response_time,
                'max_response_time': max_response_time,
                'total_time': sum(response_times)
            },
            'language_stats': language_stats,
            'detailed_results': self.results  # 包含详细结果
        }
        
        return report
    
    def save_report(self, report: Dict, output_path: str = "ocr_test_report.json"):
        """保存测试报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"📄 测试报告已保存: {output_path}")
    
    def print_summary(self, report: Dict):
        """打印测试摘要"""
        print("\n" + "="*60)
        print("📊 OCR API 测试报告")
        print("="*60)
        
        print(f"🌐 API地址: {report['api_url']}")
        print(f"📅 测试时间: {report['timestamp']}")
        print(f"📈 总样本数: {report['total_samples']}")
        print(f"✅ 成功样本: {report['successful_samples']}")
        print(f"❌ 失败样本: {report['failed_samples']}")
        print(f"📊 成功率: {report['success_rate']:.2%}")
        print(f"🎯 平均准确率: {report['avg_accuracy']:.2%}")
        
        print(f"\n⏱️  性能统计:")
        print(f"   平均响应时间: {report['performance']['avg_response_time']:.2f}秒")
        print(f"   最快响应时间: {report['performance']['min_response_time']:.2f}秒")
        print(f"   最慢响应时间: {report['performance']['max_response_time']:.2f}秒")
        
        print(f"\n🌏 按语言统计:")
        for lang, stats in sorted(report['language_stats'].items()):
            success_rate = stats['success'] / stats['total'] if stats['total'] > 0 else 0
            print(f"   {lang}: 成功率 {success_rate:.2%}, 准确率 {stats['avg_accuracy']:.2%}, 平均响应 {stats['avg_response_time']:.2f}秒")

def main():
    """主函数"""
    print("🔧 OCR API 测试工具")
    print("="*60)
    
    # 配置
    api_url = "http://localhost:16110"
    dataset_path = "/root/lhy/paddleocr/benchmarks/synthetic_30_samples_extended"
    max_workers = 4
    sample_size = 100  # 测试样本数，None表示全部
    
    # 创建测试器
    tester = OCRAPITester(api_url)
    
    # 测试数据集
    tester.test_dataset(dataset_path, max_workers=max_workers, sample_size=sample_size)
    
    # 生成报告
    report = tester.generate_report()
    tester.save_report(report)
    tester.print_summary(report)

if __name__ == "__main__":
    main()
