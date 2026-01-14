#!/usr/bin/env python3
"""Simple aggregation placeholder"""
import os


def main():
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(base, 'data')
    gen_dir = os.path.join(data_dir, 'generated')
    ground_truth_path = os.path.join(gen_dir, 'ground_truth.txt')
    output_path = os.path.join(gen_dir, 'output.txt')

    if not (os.path.exists(ground_truth_path) and os.path.exists(output_path)):
        print('Missing generated files. Run data generator first.')
        return 1

    with open(ground_truth_path, 'r', encoding='utf-8') as f:
        gt = f.read()
    with open(output_path, 'r', encoding='utf-8') as f:
        out = f.read()

    # Simple summary: print lengths and a naive match count
    summary = {
        'ground_truth_len': len(gt),
        'output_len': len(out),
        'matches': sum(1 for a, b in zip(gt, out) if a == b),
    }
    print('Summary:', summary)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
