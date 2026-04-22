"""
用于白班和日班表的导入（多线程优化版）
"""
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import os
import re


class MiningDataProcessor:
    def __init__(self, version: str = "new"):
        self.version = version
        try:
            import config_loader
            self.load_map: dict[str, int] = config_loader.get_device_load_map(version)
            if not self.load_map:
                raise FileNotFoundError
        except Exception:
            if version == "old":
                # 2024年9月前的装载量（旧版）
                self.load_map = {
                    'NTE240': 80,
                    'LIEBHERR T264': 80,
                    'EH4000': 80,
                    'MT4400AC': 80,
                    'TR100': 32,
                    'TEREX 60': 20,
                    'Terex 60': 20,
                    'TR60': 20,
                    'MT-10': 20,
                    'XDM100': 32,
                    'XDE120': 40,
                    'XDE130': 45,
                    'T-264':80,
                    'SANY SET150S':52,
                    'CAT773':20

                }
            else:
                # 2024年9月后的装载量（新版）
                self.load_map = {
                    'NTE240': 85,
                    'EH4000': 85,
                    'LIEBHERR T264': 80,
                    'TR100': 35,
                    'TEREX 60': 22,
                    'Terex 60': 22,
                    'TR60': 22,
                    'XDM100': 35,
                    'XDE120': 43,
                    'XDE130': 43,
                    'T-264': 80,
                    'SANY SET150S': 52,
                    'CAT773': 20
                }

    # ---------------------------
    # 基础工具函数
    # ---------------------------
    def parse_filename(self, filename):
        """从文件名中提取日期、班次"""
        date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', filename)
        if not date_match:
            raise ValueError(f"文件名中未找到日期: {filename}")

        date_str = date_match.group(1)
        date_val = datetime.strptime(date_str, "%Y.%m.%d").date()

        if "白班" in filename:
            shift = "Day"
        elif "夜班" in filename:
            shift = "Night"
        else:
            shift = ""

        return date_val, shift

    def get_load_capacity(self, truck_name):
        """根据矿卡名称模糊匹配装载量"""
        if pd.isna(truck_name):
            return 0

        truck_name_upper = str(truck_name).upper()
        for model, capacity in self.load_map.items():
            if model.upper() in truck_name_upper:
                return capacity
        return 0

    def safe_str(self, val):
        """安全转字符串"""
        if pd.isna(val):
            return ""
        return str(val).strip()

    def safe_number(self, val, default=0):
        """
        安全转数字：
        - 标量 -> 数字
        - Series -> 取第一个非空值
        - 空值/异常 -> default
        """
        if isinstance(val, pd.Series):
            val = val.dropna()
            if len(val) == 0:
                return default
            val = val.iloc[0]

        if pd.isna(val):
            return default

        num = pd.to_numeric(val, errors='coerce')
        if pd.isna(num):
            return default
        return float(num)

    def find_first_matching_column(self, columns, keywords):
        """
        在列名中按关键字模糊匹配，返回第一个匹配列名
        keywords: list[str]
        """
        for col in columns:
            col_str = self.safe_str(col)
            if all(k in col_str for k in keywords):
                return col
        return None

    # ---------------------------
    # 处理第一个sheet
    # ---------------------------
    def process_sheet1(self, df_raw, date_val, shift_val):
        """
        第一个sheet：
        - 解析矿卡运行数据
        - 解析生产数据
        """
        if df_raw.empty or df_raw.shape[0] < 7:
            return pd.DataFrame(), pd.DataFrame()

        # 1. 找最后一行：A列最后非空
        col_a = df_raw.iloc[:, 0]
        non_empty_a = col_a[col_a.notna()]
        if len(non_empty_a) == 0:
            return pd.DataFrame(), pd.DataFrame()

        last_row_idx = non_empty_a.index[-1]

        # 2. 找最后一列：第6行匹配“总趟数”，前一列为最后一列
        row6 = df_raw.iloc[5, :]
        total_col_idx = None
        for idx, val in row6.items():
            if "总趟数" in self.safe_str(val):
                total_col_idx = idx
                break

        if total_col_idx is not None:
            last_col_idx = total_col_idx - 1
        else:
            last_col_idx = df_raw.shape[1] - 1

        # 3. 构造复合表头
        header6 = df_raw.iloc[5, :last_col_idx + 1].ffill()
        header7 = df_raw.iloc[6, :last_col_idx + 1]

        combined_headers = []
        for h6, h7 in zip(header6, header7):
            h6_str = self.safe_str(h6)
            h7_str = self.safe_str(h7)
            combined_headers.append(f"{h6_str}｜{h7_str}")

        # 4. 数据区：第8行开始
        data = df_raw.iloc[7:last_row_idx + 1, :last_col_idx + 1].copy()
        if data.empty:
            return pd.DataFrame(), pd.DataFrame()

        data.columns = combined_headers

        # 第一列固定为矿卡名称
        first_col = data.columns[0]
        data = data.rename(columns={first_col: "矿卡名称"})

        # 5. 找运行指标列
        hour_start_col = self.find_first_matching_column(data.columns, ["小时数", "开始"])
        hour_end_col = self.find_first_matching_column(data.columns, ["小时数", "结束"])
        km_start_col = self.find_first_matching_column(data.columns, ["公里数", "开始"])
        km_end_col = self.find_first_matching_column(data.columns, ["公里数", "结束"])
        company_col = self.find_first_matching_column(data.columns, ["公司"])

        running_rows = []
        production_rows = []

        # 哪些列属于“生产列”
        exclude_keywords = ["小时数", "公里数", "总趟数", "备注", "开始", "结束", "公司"]

        for _, row in data.iterrows():
            truck_name = self.safe_str(row["矿卡名称"])

            # 修复原逻辑 bug：
            # 原代码: if not truck_name and "Нийт" not in truck_name:
            # 当 truck_name="" 时，"Нийт" not in truck_name 恒为 True
            # 这里按你的意图应该过滤空值和合计行
            if not truck_name or "Нийт" in truck_name:
                continue

            h_start = self.safe_number(row[hour_start_col]) if hour_start_col in data.columns else 0
            h_end = self.safe_number(row[hour_end_col]) if hour_end_col in data.columns else 0
            k_start = self.safe_number(row[km_start_col]) if km_start_col in data.columns else 0
            k_end = self.safe_number(row[km_end_col]) if km_end_col in data.columns else 0
            company = self.safe_str(row[company_col]) if company_col in data.columns else ""

            if not company:
                continue

            total_trips = 0
            capacity = self.get_load_capacity(truck_name)

            for col in data.columns:
                if col == "矿卡名称":
                    continue

                col_str = self.safe_str(col)

                # 排除运行类列，只保留“挖机｜矿石类型”类列
                if any(k in col_str for k in exclude_keywords):
                    continue

                if "｜" not in col_str:
                    continue

                parts = col_str.split("｜", 1)
                excavator_name = self.safe_str(parts[0])
                ore_type = self.safe_str(parts[1])

                if not excavator_name and not ore_type:
                    continue

                trips = self.safe_number(row[col], default=0)

                if trips > 0:
                    production = trips * capacity
                    production_rows.append({
                        "日期": date_val,
                        "班次": shift_val,
                        "矿卡名称": truck_name,
                        "挖机名称": excavator_name,
                        "矿石类型": ore_type,
                        "数量": trips,
                        "产量": production
                    })
                    total_trips += trips

            running_rows.append({
                "日期": date_val,
                "班次": shift_val,
                "设备名称": truck_name,
                "公司": company,
                "小时数仪表开始": h_start,
                "小时数仪表结束": h_end,
                "运行小时数": h_end - h_start,
                "公里数仪表开始": k_start,
                "公里数仪表结束": k_end,
                "运行里程": k_end - k_start,
                "趟数": total_trips
            })

        running_df = pd.DataFrame(running_rows)
        production_df = pd.DataFrame(production_rows)
        return running_df, production_df

    # ---------------------------
    # 处理第二个sheet
    # ---------------------------
    def process_sheet2(self, df_raw, date_val, shift_val):
        """
        第二个sheet:
        B列设备名称, C列公司, F列小时数开始, G列小时数结束
        输出到运行数据表
        """
        result_rows = []

        # 默认从第4行开始
        start_row = 3

        for i in range(start_row, len(df_raw)):
            device_name = self.safe_str(df_raw.iloc[i, 1])  # B列
            company = self.safe_str(df_raw.iloc[i, 2])      # C列
            h_start = self.safe_number(df_raw.iloc[i, 5])   # F列
            h_end = self.safe_number(df_raw.iloc[i, 6])     # G列

            if not device_name:
                continue

            result_rows.append({
                "日期": date_val,
                "班次": shift_val,
                "设备名称": device_name,
                "公司": company,
                "小时数仪表开始": h_start,
                "小时数仪表结束": h_end,
                "运行小时数": h_end - h_start,
                "公里数仪表开始": 0,
                "公里数仪表结束": 0,
                "运行里程": 0,
                "趟数": 0
            })

        return pd.DataFrame(result_rows)

    # ---------------------------
    # 单文件处理
    # ---------------------------
    def process_single_file(self, file_path, output_file=None):
        filename = os.path.basename(file_path)
        date_val, shift_val = self.parse_filename(filename)

        # 只打开一次 Excel 文件
        xls = pd.ExcelFile(file_path)

        if len(xls.sheet_names) < 2:
            raise ValueError("文件中少于2个sheet，请检查Excel结构。")

        # 用同一个 xls 解析，避免重复打开文件
        df_sheet1 = pd.read_excel(xls, sheet_name=0, header=None)
        running_df_1, production_df = self.process_sheet1(df_sheet1, date_val, shift_val)

        df_sheet2 = pd.read_excel(xls, sheet_name=1, header=None)
        running_df_2 = self.process_sheet2(df_sheet2, date_val, shift_val)

        # 合并运行数据
        running_df = pd.concat([running_df_1, running_df_2], ignore_index=True)

        # 输出单文件结果
        if output_file:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                running_df.to_excel(writer, sheet_name='运行数据', index=False)
                production_df.to_excel(writer, sheet_name='生产数据', index=False)

        return running_df, production_df

    # ---------------------------
    # 收集待处理文件
    # ---------------------------
    def collect_excel_files(self, folder_path):
        file_list = []
        for root, dirs, files in os.walk(folder_path):
            for filename in files:
                if filename.startswith("~$"):
                    continue
                if not filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
                    continue
                if "白班" not in filename and "夜班" not in filename:
                    continue

                file_path = os.path.join(root, filename)
                file_list.append(file_path)
        return file_list

    # ---------------------------
    # 线程任务包装
    # ---------------------------
    def process_single_file_safe(self, file_path, folder_path=None):
        """
        线程池任务函数：
        成功返回 (True, file_path, running_df, production_df, None)
        失败返回 (False, file_path, None, None, error_msg)
        """
        try:
            running_df, production_df = self.process_single_file(file_path)
            return True, file_path, running_df, production_df, None
        except Exception as e:
            return False, file_path, None, None, str(e)

    # ---------------------------
    # 文件夹处理（多线程）
    # ---------------------------
    def process_folder(self, folder_path, output_file, max_workers=4):
        all_running = []
        all_production = []
        success_files = 0

        file_list = self.collect_excel_files(folder_path)
        total_files = len(file_list)

        if total_files == 0:
            print("未找到符合条件的 Excel 文件。")
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                pd.DataFrame().to_excel(writer, sheet_name='运行数据', index=False)
                pd.DataFrame().to_excel(writer, sheet_name='生产数据', index=False)
            return

        print(f"共发现 {total_files} 个待处理文件，启动 {max_workers} 个线程...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {
                executor.submit(self.process_single_file_safe, file_path, folder_path): file_path
                for file_path in file_list
            }

            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                rel_path = os.path.relpath(file_path, folder_path)

                try:
                    ok, _, running_df, production_df, error_msg = future.result()
                    if ok:
                        all_running.append(running_df)
                        all_production.append(production_df)
                        success_files += 1
                        print(f"处理成功: {rel_path}")
                    else:
                        print(f"处理失败: {rel_path} -> {error_msg}")
                except Exception as e:
                    print(f"处理异常: {rel_path} -> {e}")

        final_running = pd.concat(all_running, ignore_index=True) if all_running else pd.DataFrame()
        final_production = pd.concat(all_production, ignore_index=True) if all_production else pd.DataFrame()

        # 按时间排序
        if not final_running.empty:
            final_running = final_running.sort_values(by=["日期", "班次"], kind="stable")
        if not final_production.empty:
            final_production = final_production.sort_values(by=["日期", "班次"], kind="stable")

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            final_running.to_excel(writer, sheet_name='运行数据', index=False)
            final_production.to_excel(writer, sheet_name='生产数据', index=False)

        print(f"汇总完成，输出文件：{output_file}")
        print(f"统计信息：共处理 {total_files} 个文件，成功 {success_files} 个，失败 {total_files - success_files} 个")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="处理矿卡数据")
    parser.add_argument("input_file", help="输入Excel文件路径")
    parser.add_argument("--workers", type=int, default=min(8, (os.cpu_count() or 4) * 2),
                        help="线程数，默认 min(8, CPU*2)")
    parser.add_argument("--version", choices=["new", "old"], default="new",
                        help="装载量映射版本，new（默认）或 old")

    args = parser.parse_args()
    input_file = args.input_file
    workers = args.workers
    version = args.version

    output_file = r"合并产量.xlsx"
    processor = MiningDataProcessor(version=version)

    if os.path.isdir(input_file):
        print(f"正在处理文件夹: {input_file}")
        output_file = os.path.join(input_file, os.path.basename(output_file))
        processor.process_folder(input_file, output_file, max_workers=workers)
    else:
        parent_folder = os.path.dirname(input_file)
        output_file = os.path.join(parent_folder, os.path.basename(output_file))
        processor.process_single_file(input_file, output_file)
        print(f"单文件处理完成，输出文件：{output_file}")