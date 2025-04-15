import json
import os

def read_first_entries():
    try:
        # 首先尝试读取yuan.json
        if os.path.exists('arxiv/yuan.json'):
            with open('arxiv/yuan.json', 'r', encoding='utf-8') as f:
                print("正在读取yuan.json文件...")
                paper = json.load(f)
                print(f"\n论文:")
                print(f"标题: {paper.get('title', 'N/A')}")
                print(f"作者: {paper.get('authors', 'N/A')}")
                print(f"分类: {paper.get('categories', 'N/A')}")
                print(f"摘要: {paper.get('abstract', 'N/A')[:200]}...")  # 只显示摘要的前200个字符
        else:
            # 如果yuan.json不存在，尝试读取原始文件
            with open('arxiv/arxiv-metadata-oai-snapshot.json', 'r', encoding='utf-8') as f:
                print("正在读取arxiv-metadata-oai-snapshot.json文件...")
                for i, line in enumerate(f):
                    if i >= 5:  # 只读取前5条记录
                        break
                    try:
                        paper = json.loads(line.strip())
                        print(f"\n论文 {i+1}:")
                        print(f"标题: {paper.get('title', 'N/A')}")
                        print(f"作者: {paper.get('authors', 'N/A')}")
                        print(f"分类: {paper.get('categories', 'N/A')}")
                        print(f"摘要: {paper.get('abstract', 'N/A')[:200]}...")  # 只显示摘要的前200个字符
                    except json.JSONDecodeError as e:
                        print(f"解析第 {i+1} 条记录时出错: {e}")
                    except Exception as e:
                        print(f"处理第 {i+1} 条记录时出现未知错误: {e}")
    except FileNotFoundError:
        print("找不到文件，请确保文件路径正确")
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    read_first_entries() 