import os.path

import pandas as pd
import datetime


def process_engine_data(file_path, output_path):
    # 1. 读取数据
    df = pd.read_excel(file_path)

    # 确保日期格式正确
    df['日期'] = pd.to_datetime(df['日期'])

    # 定义班次顺序（白班在前，夜班在后）
    shift_order = {'Day': 0, 'Night': 1}

    # 2. 确定时间范围（当月的第一天到最后一天）
    start_date = df['日期'].min().replace(day=1)
    # 获取当月最后一天
    next_month = start_date.replace(day=28) + datetime.timedelta(days=4)
    end_date = next_month - datetime.timedelta(days=next_month.day)

    # 生成完整的日期和班次序列
    all_dates = pd.date_range(start_date, end_date, freq='D')
    all_shifts = ['Day', 'Night']

    # 3. 为每个设备构建完整的时间表骨架
    # 首先获取所有唯一的设备信息
    equipments = df[['设备名称', '设备编号']].drop_duplicates()

    full_data_list = []
    for _, equip in equipments.iterrows():
        # 为每个设备创建一个日期和班次的全笛卡尔积
        temp_df = pd.MultiIndex.from_product(
            [all_dates, all_shifts],
            names=['日期', '班次']
        ).to_frame(index=False)

        temp_df['设备名称'] = equip['设备名称']
        temp_df['设备编号'] = equip['设备编号']
        full_data_list.append(temp_df)

    grid_df = pd.concat(full_data_list)

    # 4. 合并原始数据
    # 将原始数据与骨架合并
    merged_df = pd.merge(grid_df, df, on=['日期', '班次', '设备名称', '设备编号'], how='left')

    # 5. 排序并填充缺失数据
    # 关键：排序必须严格按照 设备 -> 日期 -> 班次等级
    merged_df['班次权重'] = merged_df['班次'].map(shift_order)
    merged_df = merged_df.sort_values(['设备编号', '日期', '班次权重']).reset_index(drop=True)

    # 前向填充 G列（发动机开始时间）
    # 这样如果 1号到3号没数据，1号的值会自动覆盖到2号全天
    merged_df['发动机小时数开始'] = merged_df.groupby('设备编号')['发动机小时数开始'].ffill()

    # 6. 计算 H列（发动机结束时间）
    # 规则：当前结束 = 同设备下一次的开始
    # 使用 groupby(设备).shift(-1) 将下一行的数据上移
    merged_df['发动机小时数结束'] = merged_df.groupby('设备编号')['发动机小时数开始'].shift(-1)

    # 7. 处理月底最后一天的数据
    # 如果最后一行没有“下一次开始时间”，规则通常是令其等于自身的开始时间（或根据需求修改）
    merged_df['发动机小时数结束'] = merged_df['发动机小时数结束'].fillna(merged_df['发动机小时数开始'])

    # 8. 整理格式并保存
    # 移除辅助列并重命名
    result_df = merged_df[['日期', '班次', '设备名称', '设备编号', '发动机小时数开始', '发动机小时数结束']]
    result_df.sort_values(['设备编号', '日期', '班次'], inplace=True)
    result_df['日期'] = result_df['日期'].dt.strftime('%Y-%m-%d')
    # 去除重复
    result_df = result_df.drop_duplicates(subset=['设备编号', '日期', '班次'], keep='first')
    # 去除缺失值
    result_df = result_df.dropna(subset=['发动机小时数开始'])
    # 保存结果
    result_df.to_excel(output_path, index=False)
    print(f"处理完成，结果已保存至: {output_path}")

# 使用示例
filename = "/Users/kearney/Library/CloudStorage/OneDrive-个人/工作/01蒙古业务部/[2]子公司资料/01北山公司/01生产数据/2019/2019.9/柴油/Fuel的副本.xlsx"
output_file = os.path.join(os.path.dirname(filename), "output.xlsx")
process_engine_data(filename, output_file)
