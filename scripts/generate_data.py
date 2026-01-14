#!/usr/bin/env python3
"""End-to-end data generation placeholder: from data/raw/input.txt to data/generated/ground_truth.txt and data/generated/output.txt"""
import os

def ensure_dirs(base):
    raw = os.path.join(base, 'raw')
    gen = os.path.join(base, 'generated')
    os.makedirs(raw, exist_ok=True)
    os.makedirs(gen, exist_ok=True)
    return raw, gen


def main():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(base, 'data')
    raw_dir, gen_dir = ensure_dirs(data_dir)

    input_path = os.path.join(raw_dir, 'input.txt')
    if not os.path.exists(input_path):
        with open(input_path, 'w', encoding='utf-8') as f:
            f.write('Hello World OCR Benchmark\nThis is a sample input for OCR benchmarking.')
        
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    ground_truth_path = os.path.join(gen_dir, 'ground_truth.txt')
    output_path = os.path.join(gen_dir, 'output.txt')

    with open(ground_truth_path, 'w', encoding='utf-8') as f:
        f.write(text)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text.upper())

    print('Data generated:')
    print('  ground_truth:', ground_truth_path)
    print('  output      :', output_path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
