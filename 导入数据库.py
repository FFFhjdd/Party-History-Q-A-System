

import pandas as pd
from py2neo import Graph, Node, Relationship, NodeMatcher

# 连接到 Neo4j 数据库
g = Graph("bolt://localhost:7687", auth=("neo4j", "123456"))
matcher = NodeMatcher(g)

# 初始化存储实体的列表
person = []
event = []
introduction = []

def create_nodes_and_relationships(df):
    for index, row in df.iterrows():
        data = row['文本内容']
        relationships = row[1:]  # 获取所有关系列

        result = {}
        for relation in relationships.dropna():  # 忽略空的关系单元格
            row_content = relation.split('},')
            entity1, entity2, rel_type = row_content

            # 解析实体1
            B = entity1.split(',')[0][2:]
            E = entity1.split(',')[1][0:-1]
            label1 = entity1.split(',')[-1].strip('}')
            entity1_text = data[int(B):int(E) + 1].strip()
            result[label1] = entity1_text
            if label1 == '人物' and entity1_text not in person:
                person.append(entity1_text)

            # 解析实体2
            B = entity2.split(',')[0][2:]
            E = entity2.split(',')[1][0:-1]
            label2 = entity2.split(',')[-1].strip('}')
            entity2_text = data[int(B):int(E) + 1].strip()
            result[label2] = entity2_text
            if label2 == '人物' and entity2_text not in person:
                person.append(entity2_text)

            # 创建节点和关系
            nodelist = list(matcher.match(label1, name=entity1_text))
            if len(nodelist) > 0:
                entity1_node = nodelist[0]
            else:
                entity1_node = Node(label1, name=entity1_text)
                g.create(entity1_node)

            nodelist = list(matcher.match(label2, name=entity2_text))
            if len(nodelist) > 0:
                entity2_node = nodelist[0]
            else:
                entity2_node = Node(label2, name=entity2_text)
                g.create(entity2_node)

            relationship = Relationship(entity1_node, rel_type, entity2_node)
            g.create(relationship)

        introduction.append(result)


# 读取 Excel 文件
file_path = 'data.xlsx'
df = pd.read_excel(file_path)

# 执行创建节点和关系的函数
create_nodes_and_relationships(df)

