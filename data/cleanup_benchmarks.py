#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
清理benchmarks目录，只保留与synthetic_30_samples_extended相关的核心文件
"""

import os
import shutil
from pathlib import Path

def cleanup_benchmarks():
    """清理benchmarks目录"""
    print("🧹 开始清理benchmarks目录...")
    
    # 需要保留的核心文件
    keep_files = {
        # 核心生成脚本
        'gen_synthetic_extended.py',
        'gen_30_samples_batch1.py', 
        'gen_30_samples_batch2.py',
        
        # 数据集目录
        'synthetic_30_samples_extended',
        
        # 文档文件
        'EXTENDED_SYNTHETIC_README.md',
        
        # 最终修复脚本（只保留最新的）
        'fix_mongolian_simple.py',
        'fix_fonts_final_solution.py',
        
        # 核心验证脚本
        'verify_30_samples.py',
        
        # 字体目录
        'fonts',
        
        # 其他核心文件
        'run_benchmark_synthetic.py',
        'test_extended_synthetic.py'
    }
    
    # 需要删除的文件模式
    delete_patterns = [
        # 临时修复脚本
        'fix_fonts_*.py',
        'fix_mongolian_*.py', 
        'fix_mn_lo_*.py',
        'fix_chinese_*.py',
        
        # 验证脚本
        'verify_*.py',
        'final_verification*.py',
        
        # 临时数据集
        'synthetic_*',
        'simple_dataset',
        
        # 临时结果文件
        '*.json',
        '*.sh',
        
        # 其他临时文件
        'cleanup_*.py',
        'compare_*.py',
        'download_*.py',
        'evaluate_*.py',
        'gen_*.py',  # 除了核心的
        'make_*.py',
        'merge_*.py',
        'run_*.py',  # 除了核心的
        'simple_*.py',
        'test_*.py'  # 除了核心的
    ]
    
    # 获取当前目录
    current_dir = Path('.')
    
    # 统计信息
    deleted_files = []
    deleted_dirs = []
    kept_files = []
    
    print("📋 分析文件...")
    
    # 遍历所有文件和目录
    for item in current_dir.iterdir():
        if item.name.startswith('.'):
            continue
            
        should_keep = False
        
        # 检查是否在保留列表中
        if item.name in keep_files:
            should_keep = True
            kept_files.append(item.name)
        else:
            # 检查是否匹配删除模式
            for pattern in delete_patterns:
                if pattern.endswith('*'):
                    prefix = pattern[:-1]
                    if item.name.startswith(prefix):
                        should_keep = False
                        break
                else:
                    if item.name == pattern:
                        should_keep = False
                        break
            else:
                # 如果不在删除模式中，保留
                should_keep = True
                kept_files.append(item.name)
        
        if not should_keep:
            try:
                if item.is_file():
                    item.unlink()
                    deleted_files.append(item.name)
                    print(f"🗑️  删除文件: {item.name}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_dirs.append(item.name)
                    print(f"🗑️  删除目录: {item.name}")
            except Exception as e:
                print(f"❌ 删除失败 {item.name}: {e}")
    
    # 输出统计信息
    print(f"\n📊 清理完成!")
    print(f"✅ 保留文件: {len(kept_files)}")
    print(f"🗑️  删除文件: {len(deleted_files)}")
    print(f"🗑️  删除目录: {len(deleted_dirs)}")
    
    print(f"\n📁 保留的核心文件:")
    for file in sorted(kept_files):
        print(f"  ✅ {file}")
    
    print(f"\n🗑️  删除的文件:")
    for file in sorted(deleted_files + deleted_dirs):
        print(f"  ❌ {file}")

if __name__ == "__main__":
    cleanup_benchmarks()

