import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import subprocess
import shutil
import tarfile
import xml.etree.ElementTree as ET
import re

def create_folder(folder_name):
    """建立資料夾"""
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
    return os.path.abspath(folder_name)

def delete_folders(deletelist):
    """
    刪除資料夾
    deletelist(list):需要為皆為路徑的list
    """
    for folder_name in deletelist: 
        if os.path.exists(folder_name): # 檢查資料夾是否存在
            shutil.rmtree(folder_name) # 刪除資料夾及其內容
        else:
            print(f"資料夾 '{folder_name}' 不存在。")

def getdatelist(time1, time2):
    '''
    建立日期清單
    time1、time2(str):為%Y-%M-%D格式的日期字串
    '''
    if time1 > time2:
        starttime = time2
        endtime = time1
    else:
        starttime = time1
        endtime = time2

    date_range = pd.date_range(start=starttime, end=endtime)
    datelist = [d.strftime("%Y%m%d") for d in date_range]
    return datelist

def freewaydatafolder(datatype):
    # savelocation = create_folder(os.path.join(os.getcwd(),'..','Output', datatype))
    savelocation = create_folder(os.path.join(os.getcwd(),'..','01_資料初步彙整','03_高公局資料', datatype))
    rawdatafolder = create_folder(os.path.join(savelocation, '0_rawdata'))
    mergefolder = create_folder(os.path.join(savelocation, '1_merge'))
    excelfolder = create_folder(os.path.join(savelocation, '2_excel'))
    return rawdatafolder, mergefolder, excelfolder

def delete_folders_permanently(deletelist):
    """
    永久刪除資料夾及其內容，不放入資源回收筒
    deletelist (list): 需要刪除的資料夾路徑列表
    """
    for item in deletelist:
        if os.path.isdir(item):  # 檢查是否為資料夾
            try:
                shutil.rmtree(item)  # 永久刪除資料夾
                print(f"已永久刪除資料夾： {item}")
            except OSError as e:
                print(f"刪除資料夾 {item} 時發生錯誤： {e}")
        elif os.path.isfile(item):  # 檢查是否為檔案
            try:
                os.remove(item)  # 永久刪除檔案
                print(f"已永久刪除檔案： {item}")
            except OSError as e:
                print(f"刪除檔案 {item} 時發生錯誤： {e}")
        else:
            print(f"{item} 不是檔案或資料夾。")

def download_etag(etagurl, etagdownloadpath):
    """
    下載指定網址的 XML 檔案到指定位置。

    Args:
        etagurl (str): 要下載的 XML 檔案網址。
        etagdownloadpath (str): 檔案下載後的儲存路徑（包含檔案名稱）。
    """

    try:
        response = requests.get(etagurl, stream=True)
        response.raise_for_status()  # 檢查 HTTP 狀態碼，如有錯誤則拋出異常

        with open(etagdownloadpath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    except requests.exceptions.RequestException as e:
        print(f"下載時發生錯誤：{e}")
    except Exception as e:
        print(f"發生錯誤：{e}")

def read_xml(xml_file_path):
    """
    讀取並解析 XML 檔案。

    Args:
        xml_file_path (str): XML 檔案路徑。

    Returns:
        ElementTree.Element: XML 文件的根節點。
        None: 如果解析失敗。
    """
    # try:
    #     tree = ET.parse(xml_file_path)
    #     root = tree.getroot()
    #     return root
    try:
        with open(xml_file_path, 'r', encoding='utf-8') as f:  # 指定編碼
            xml_content = f.read()
        return xml_content
    except FileNotFoundError:
        print(f"檔案未找到：{xml_file_path}")
        return None
    except ET.ParseError as e:
        print(f"解析 XML 檔案時發生錯誤：{e}")
        return None

def etag_xml_to_dataframe(xml_content):
    """
    將 XML 內容轉換為 Pandas DataFrame。

    Args:
        xml_content (str): XML 內容字串。

    Returns:
        pandas.DataFrame: 轉換後的 DataFrame。
        None: 如果解析失敗。
    """
    try:
        root = ET.fromstring(xml_content)  # 從字串解析 XML

        data = []
        for etag in root.findall('.//{http://traffic.transportdata.tw/standard/traffic/schema/}ETag'):
            etag_data = {}
            for element in etag:
                tag_name = element.tag.split('}')[-1]  # 去除命名空間
                if tag_name == 'RoadSection':  # 處理 RoadSection
                    for section_element in element:
                        etag_data[section_element.tag] = section_element.text
                else:
                    etag_data[tag_name] = element.text
            data.append(etag_data)

        df = pd.DataFrame(data)
        df.columns = ['ETagGantryID','LinkID', 'LocationType', 'PositionLon', 'PositionLat', 'RoadID', 'RoadName', 'RoadClass', 'RoadDirection', 'Start','End', 'LocationMile']
        return df

    except ET.ParseError as e:
        print(f"解析 XML 內容時發生錯誤：{e}")
        return None
    except Exception as e:
        print(f"發生錯誤：{e}")
        return None

def etag_getdf():
    etagfolder = create_folder(os.path.join(os.getcwd(),'..','Output', 'ETag'))
    etagurl = 'https://tisvcloud.freeway.gov.tw/history/motc20/ETag.xml'
    etagdownloadpath = os.path.join(etagfolder, 'ETag.xml')
    download_etag(etagurl=etagurl, etagdownloadpath=etagdownloadpath)
    etagxml = read_xml(etagdownloadpath)
    etag = etag_xml_to_dataframe(etagxml)

    etag.to_excel(os.path.join(etagfolder,'Etag.xlsx'), index = False, sheet_name='ETag')
    return etag

def extract_tar_gz(tar_gz_file, extract_path):
    try:
        with tarfile.open(tar_gz_file, 'r:gz') as tar:
            tar.extractall(path=extract_path)
    except Exception as e:
        print(f"解壓縮 {tar_gz_file} 失敗：{e}")

def download_and_extract(url, datatype, date, downloadfolder, keep = False):
    '''針對高公局交通資料庫的格式進行下載'''
    downloadurl = f"{url}/{datatype}_{date}.tar.gz"
    destfile = os.path.join(downloadfolder, f"{datatype}_{date}.tar.gz")

    response = requests.get(downloadurl)
    
    if response.status_code == 200:
        with open(destfile, 'wb') as file:
            file.write(response.content)
        extractpath = create_folder(os.path.join(downloadfolder, date))
        extract_tar_gz(destfile, extractpath)
        if keep == False:
            os.remove(destfile)
    else:
        extractpath = create_folder(os.path.join(downloadfolder, date))
        hourlist = [f"{i:02d}" for i in range(24)]
        if datatype == 'M06A':
            for hour in hourlist:
                downloadurl = f"{url}/{date}/{hour}/TDCS_{datatype}_{date}_{hour}0000.csv"
                destfile = os.path.join(extractpath, f"TDCS_{datatype}_{date}_{hour}0000.csv")
                response = requests.get(downloadurl, stream=True) # 發送 GET 請求下載檔案
                if response.status_code == 200:
                    with open(destfile, 'wb') as file:
                        file.write(response.content)  # 直接寫入整個回應內容
                else:
                    print(f"下載失敗: {downloadurl}, 狀態碼: {response.status_code}")

        else :
            for hour in hourlist:
                minlist = [f"{i:02d}" for i in range(0, 60, 5)]
                for minute in minlist:
                    downloadurl = f"{url}/{date}/{hour}/TDCS_{datatype}_{date}_{hour}{minute}00.csv"
                    destfile = os.path.join(extractpath, f"TDCS_{datatype}_{date}_{hour}{minute}00.csv")

                    response = requests.get(downloadurl, stream=True) # 發送 GET 請求下載檔案
                    
                    if response.status_code == 200:
                        with open(destfile, 'wb') as file:
                            file.write(response.content)  # 直接寫入整個回應內容
                    else:
                        print(f"下載失敗: {downloadurl}, 狀態碼: {response.status_code}")

    return extractpath

def findfiles(filefolderpath, filetype='.csv'):
    """
    尋找指定路徑下指定類型的檔案，並返回檔案路徑列表。

    Args:
        filefolderpath (str): 指定的檔案路徑。
        filetype (str, optional): 要尋找的檔案類型，預設為 '.csv'。

    Returns:
        list: 包含所有符合條件的檔案路徑的列表。
    """

    filelist = []  # 建立一個空列表來儲存檔案路徑

    # 使用 os.walk 遍歷資料夾及其子資料夾
    for root, _, files in os.walk(filefolderpath):
        for file in files:
            if file.endswith(filetype):  # 檢查檔案是否以指定類型結尾
                file_path = os.path.join(root, file)  # 建立完整的檔案路徑
                filelist.append(file_path)  # 將檔案路徑添加到列表中

    return filelist

def combinefile(filelist, datatype='M03A'):
    """
    更有效率地合併多個CSV檔案。

    Args:
        filelist (list): 包含CSV檔案路徑的列表。
        datatype (str, optional): 資料類型，決定欄位名稱。預設為 'M03A'。

    Returns:
        pandas.DataFrame: 合併後的DataFrame。
    """

    # 使用字典來映射資料類型和欄位名稱，避免重複的 if/elif 判斷
    column_mapping = {
        'M03A': ['TimeStamp', 'GantryID', 'Direction', 'VehicleType', 'Volume'],
        'M04A': ['TimeStamp', 'GantryFrom', 'GantryTo', 'VehicleType', 'TravelTime', 'Volume'],
        'M05A': ['TimeStamp', 'GantryFrom', 'GantryTo', 'VehicleType', 'Speed', 'Volume'],
        'M06A': ['VehicleType', 'DetectionTimeO', 'GantryO', 'DetectionTimeD', 'GantryD', 'TripLength', 'TripEnd', 'TripInformation'],
        'M07A': ['TimeStamp', 'GantryO', 'VehicleType', 'AverageTripLength', 'Volume'],
        'M08A': ['TimeStamp', 'GantryO', 'GantryD', 'VehicleType', 'Trips']
    }

    columns = column_mapping.get(datatype)  # 使用 get() 方法，如果找不到鍵，會返回 None
    if columns is None:
        raise ValueError(f"未知的資料類型：{datatype}")

    combineddf = pd.concat(
        (pd.read_csv(i, header=None, names=columns) for i in filelist),  # 使用生成器表達式
        ignore_index=True  # 避免重複的索引
    )

    return combineddf

def THI_M03A(df):
    df = df.pivot(index=['TimeStamp', 'GantryID', 'Direction'], columns='VehicleType', values='Volume').reset_index()
    df = df.rename(columns = {
        5 : 'Vol_Trail',
        31 : 'Vol_Car',
        32 : 'Vol_Truck',
        41 : 'Vol_TourBus',
        42 : 'Vol_BTruck'
    })
    df = df.reindex(columns = ['TimeStamp', 'GantryID', 'Direction', 'Vol_Trail', 'Vol_Car', 'Vol_Truck', 'Vol_TourBus', 'Vol_BTruck'])

    df['TimeStamp'] = pd.to_datetime(df['TimeStamp'])

    df['Date'] = df['TimeStamp'].dt.date
    df['Hour'] = df['TimeStamp'].dt.hour

    df = df.groupby(['Date','Hour','GantryID','Direction']).agg({
            'Vol_Trail':'sum',
            'Vol_Car':'sum', 
            'Vol_Truck':'sum',
            'Vol_TourBus':'sum',
            'Vol_BTruck':'sum'}).reset_index()
    return df

# def THI_M05A(df, weighted = False):
    
#     # 將每5分鐘的資料，轉為分時資料
#     df['TimeStamp'] = pd.to_datetime(df['TimeStamp'])
#     df['Date'] = df['TimeStamp'].dt.date
#     df['Hour'] = df['TimeStamp'].dt.hour

#     df = df[df['Volume']!=0] # 需要避開Volume 為0的資料

#     if weighted == True:
#         df['Speed_time_volume'] = df['Speed'] * df['Volume']
#         df = df.groupby(['Date', 'Hour', 'GantryFrom', 'GantryTo', 'VehicleType']).agg({'Speed_time_volume':'sum', 'Volume':'sum'}).reset_index()
#         df['Speed'] = df['Speed_time_volume'] / df['Volume']
#     else :
#         df = df.groupby(['Date', 'Hour', 'GantryFrom', 'GantryTo', 'VehicleType']).agg({'Speed':'mean'}).reset_index()
    
    
#     df['Speed'] = df['Speed'].round(3)
#     df = df.pivot(index=['Date', 'Hour', 'GantryFrom', 'GantryTo'], columns='VehicleType', values='Speed').reset_index()
#     df = df.rename(columns = {
#         5 : 'Speed_Trail',
#         31 : 'Speed_Car',
#         32 : 'Speed_Truck',
#         41 : 'Speed_TourBus',
#         42 : 'Speed_BTruck'
#     })

#     df = df.fillna(0)
#     df = df.reindex(columns = ['Date', 'Hour', 'GantryFrom', 'GantryTo', 'Speed_Trail', 'Speed_Car', 'Speed_Truck', 'Speed_TourBus', 'Speed_BTruck'])
    
#     return df


def THI_M05A(df, weighted = False):
    
    # 將每5分鐘的資料，轉為分時資料
    df['TimeStamp'] = pd.to_datetime(df['TimeStamp'])
    df['Date'] = df['TimeStamp'].dt.date
    df['Hour'] = df['TimeStamp'].dt.hour

    df = df[df['Volume']!=0] # 需要避開Volume 為0的資料

    if weighted == True:
        df['Speed_time_volume'] = df['Speed'] * df['Volume']
        df = df.groupby(['Date', 'Hour', 'GantryFrom', 'GantryTo', 'VehicleType']).agg({'Speed_time_volume':'sum', 'Volume':'sum'}).reset_index()
        df['Speed'] = df['Speed_time_volume'] / df['Volume']
    else :
        df = df.groupby(['Date', 'Hour', 'GantryFrom', 'GantryTo', 'VehicleType']).agg({'Speed':'mean'}).reset_index()
    
    
    df['Speed'] = df['Speed'].round(3)
    df = df.pivot(index=['Date', 'Hour', 'GantryFrom', 'GantryTo'], columns='VehicleType', values='Speed').reset_index()
    df = df.rename(columns = {
        5 : 'Speed_Trail',
        31 : 'Speed_Car',
        32 : 'Speed_Truck',
        41 : 'Speed_TourBus',
        42 : 'Speed_BTruck'
    })

    etag = pd.read_excel(os.path.join(os.getcwd(),'..','Input',"靜態資料", "Table", "ETag整併資料.xlsx"))
    etag = etag.reindex(columns = ['ETagGantryID','UpstreamDistance','DownstreamDistance','SpeedLimit'])

    df = df.fillna(0)
    df = df.reindex(columns = ['Date', 'Hour', 'GantryFrom', 'GantryTo', 'Speed_Trail', 'Speed_Car', 'Speed_Truck', 'Speed_TourBus', 'Speed_BTruck'])

    df = df.fillna(0)
    df = df.reindex(columns = ['Date', 'Hour', 'GantryFrom', 'GantryTo', 'Speed_Trail', 'Speed_Car', 'Speed_Truck', 'Speed_TourBus', 'Speed_BTruck'])

    df['Speed'] = df[['Speed_Trail', 'Speed_Car', 'Speed_Truck', 'Speed_TourBus', 'Speed_BTruck']].replace(0, np.nan).mean(axis=1, skipna=True)
    df['Speed'] = df['Speed'].round(3)

    M05A = pd.merge(etag, df[['Date', 'Hour', 'Speed', 'GantryTo']].rename(columns = {'Speed':'UpstreamSpeed', 'GantryTo':'ETagGantryID'}), on = 'ETagGantryID', how = 'left')
    M05A = pd.merge(M05A, df[['Date', 'Hour', 'Speed', 'GantryFrom']].rename(columns = {'Speed':'DownstreamSpeed', 'GantryFrom':'ETagGantryID'}), on = ['Date', 'Hour', 'ETagGantryID'], how = 'left' )
    M05A['UpstreamTime'] = M05A['UpstreamDistance'] / M05A['UpstreamSpeed']
    M05A['DownstreamTime'] = M05A['DownstreamDistance'] / M05A['DownstreamSpeed']
    M05A['Speed'] = (M05A['UpstreamDistance'] + M05A['DownstreamDistance']) / (M05A['UpstreamTime'] + M05A['DownstreamTime'])
    M05A = M05A.reindex(columns = ['Date','Hour','ETagGantryID', 'Speed', 'SpeedLimit'])
    M05A['Speed'] = M05A['Speed'].round(3)
    
    return M05A



# def THI_M06A(df, hour = True):
#     df['DetectionTimeO'] = pd.to_datetime(df['DetectionTimeO'])
#     df['DetectionTimeD'] = pd.to_datetime(df['DetectionTimeD'])

#     df['Date'] = df['DetectionTimeO'].dt.date
#     if hour == True:
#         df['HourO'] = df['DetectionTimeO'].dt.hour
#         df['HourD'] = df['DetectionTimeD'].dt.hour
#         df = df.groupby(['Date','HourO', 'GantryO', 'HourD', 'GantryD', 'VehicleType']).size().reset_index(name='Volume')

#     df = df.groupby(['Date', 'GantryO', 'GantryD','VehicleType']).size().reset_index(name='Volume')

#     return df 

def THI_M06A_step1(df):
    '''把所有的M06A每一個路徑都拆分成每一筆M03A，並賦予他index編號'''
    df = df.reset_index()
    df["TripInformation"] = df["TripInformation"].str.split("; ")
    # 2. 使用 explode 展開每一筆紀錄
    df = df.explode("TripInformation").reset_index(drop=True)
    # 3. 拆分 DetectionTime 和 GantryID
    df[["DetectionTime", "GantryID"]] = df["TripInformation"].str.split("+", expand=True)
    df["DetectionTime"] = pd.to_datetime(df["DetectionTime"])
    df['DetectionDate'] = df["DetectionTime"].dt.date
    df['DetectionHour'] = df["DetectionTime"].dt.hour
    df = df.reindex(columns = ['index', 'VehicleType','DetectionDate','DetectionHour', 'GantryID'])
    df_grouped = df.groupby("index")["GantryID"].apply(list).reset_index()
    df = df.merge(df_grouped, on="index", suffixes=("", "_list"))
    return df  

def THI_M06A_step2(df, ramp):
    '''ramp會是由你先前選擇的分析路口進行，需要人工進行挑選，目前尚無法自動化
    df 為 THI_M06A_step1 處理玩的ETC資料
    return 的 final_df 為各匝道進出的資料'''
    # 初始化統計結果
    results = []

    # 遍歷 ramp 表，找符合條件的資料
    for _, row in ramp.iterrows():
        ramp_name, direction, pass_id, unpass_id = row

        # 篩選有經過 PassGantryID 但沒有 UnpassGantryID 的車輛
        matched_df = df[df["GantryID_list"].apply(lambda x: pass_id in x and unpass_id not in x)]
        matched_df = matched_df[matched_df['GantryID'] == pass_id]

        # 統計不同 VehicleType 在各時段的數量
        summary = matched_df.groupby(["DetectionDate","DetectionHour", "VehicleType"])["index"].nunique().reset_index(name="Count")

        # 加入 Ramp 和 Direction 資訊
        summary["Ramp"] = ramp_name
        summary["Direction"] = direction
        summary["PassGantryID"] = pass_id
        summary["UnpassGantryID"] = unpass_id

        # 加入結果
        results.append(summary)

    # 合併所有結果
    final_df = pd.concat(results, ignore_index=True)
    return final_df

def THI_M06A_step3(final_df):
    final_df = final_df.pivot_table(index=['DetectionDate', 'DetectionHour', 'Ramp', 'Direction', 'PassGantryID', 'UnpassGantryID'], 
                                    columns='VehicleType',
                                    values='Count',
                                    aggfunc='sum',  # 如果有重複的組合，進行加總
                                    fill_value=0     # 填充缺失值為 0
                                    ).reset_index()
    final_df['PCU'] = final_df[5] * 3 + final_df[31]*1 + final_df[32] *1 + final_df[41] * 1.8 + final_df[42] * 1.8
    final_df = final_df.groupby(['DetectionDate',  'DetectionHour', 'Ramp', 'Direction', 'PassGantryID', 'UnpassGantryID']).agg({5:'sum', 31:'sum', 32 : 'sum',  41:'sum', 42 :'sum',  'PCU':'sum'}).reset_index()
    final_df = final_df.rename(columns = {
        5 : 'Vol_Trail',
        31 : 'Vol_Car',
        32 : 'Vol_Truck',
        41 : 'Vol_TourBus',
        42 : 'Vol_BTruck'
    })
    final_df["Ramp&Dir"] = final_df["Ramp"] + "(" + final_df["Direction"] + ")"
    final_df['Volume'] = final_df['Vol_Trail'] + final_df['Vol_Car'] + final_df['Vol_BTruck']+ final_df['Vol_TourBus'] + final_df['Vol_Truck']

    final_df = final_df.reindex(columns = ['DetectionDate', 'DetectionHour', 'Ramp&Dir','Ramp', 'Direction', 'PassGantryID', 'UnpassGantryID', 'Vol_Trail', 'Vol_BTruck', 'Vol_TourBus', 'Vol_Car', 'Vol_Truck', 'Volume','PCU'])

    return final_df

def THI_M06A(df):
    df = THI_M06A_step1(df)

    # 讀取ramp資料
    ramp = pd.read_excel(os.path.join(os.getcwd(),'..', 'Input', 'ETag匝道選擇.xlsx'), sheet_name='Ramp', skiprows=1)
    ramp = ramp.iloc[:,:4]
    ramp = ramp.sort_values(['Ramp', 'Direction'], ascending=[True, False]).reset_index(drop = True)

    outputdf = THI_M06A_step2(df = df , ramp = ramp)
    outputdf = THI_M06A_step3(outputdf)
    return outputdf


def THI_M08A(df, hour = True):
    df['TimeStamp'] = pd.to_datetime(df['TimeStamp'])

    df['Date'] = df['TimeStamp'].dt.date
    df['Hour'] = df['TimeStamp'].dt.hour
    if hour == True:
        df = df.groupby(['Date', 'Hour', 'GantryO', 'GantryD', 'VehicleType']).size().reset_index(name='Volume')
    df = df.groupby(['Date', 'GantryO', 'GantryD','VehicleType']).size().reset_index(name='Volume')
    return df 

def THI_process(df, datatype, weighted = False, hour = True):
    if datatype == 'M03A':
        df = THI_M03A(df)
    elif datatype == 'M05A':
        df = THI_M05A(df, weighted = weighted)
    elif datatype == 'M06A':
        df = THI_M06A(df)
    elif datatype == 'M08A':
        df = THI_M08A(df, hour = True)
    return df

# def M03A_Tableau_combined(folder , etag):
#     allfiles = findfiles(filefolderpath=folder, filetype='.xlsx')
#     combineddf = pd.concat(
#         (pd.read_excel(i) for i in allfiles),  # 使用生成器表達式
#         ignore_index=True  # 避免重複的索引
#     )

#     combineddf['Day'] = combineddf["Date"].dt.day_name() #生成星期幾

#     combineddf = pd.merge(combineddf,etag[['ETagGantryID', 'RoadName','Start', 'End']].rename(columns = {'ETagGantryID':'GantryID'}) , on = 'GantryID')
#     combineddf['RoadSection'] = combineddf['Start'] + '-' + combineddf['End']

#     outputfolder = create_folder(os.path.join(folder, '..', '3_TableauData'))
#     combineddf.to_csv(os.path.join(outputfolder, 'M03A.csv'), index=False)

def M03A_Tableau_combined(folder , etag):
    allfiles = findfiles(filefolderpath=folder, filetype='.xlsx')
    combineddf = pd.concat(
        (pd.read_excel(i) for i in allfiles),  # 使用生成器表達式
        ignore_index=True  # 避免重複的索引
    )

    # 轉換為長格式（long format）
    combineddf = combineddf.melt(id_vars=["Date", "Hour", "GantryID", "Direction"], 
                        value_vars=["Vol_Trail", "Vol_Car", "Vol_Truck", "Vol_TourBus", "Vol_BTruck"],
                        var_name="VehicleType", 
                        value_name="Volume")

    # 轉換 VehicleType 名稱
    vehicle_mapping = {
        "Vol_Trail": 5,
        "Vol_Car": 31,
        "Vol_Truck": 32,
        "Vol_TourBus": 41,
        "Vol_BTruck": 42
    }

    combineddf["VehicleType"] = combineddf["VehicleType"].map(vehicle_mapping)
    combineddf["VehicleType"] = combineddf["VehicleType"].astype('int64')


    combineddf['Day'] = combineddf["Date"].dt.day_name() #生成星期幾

    combineddf = pd.merge(combineddf,etag[['ETagGantryID', 'RoadName','Start', 'End']].rename(columns = {'ETagGantryID':'GantryID'}) , on = 'GantryID')
    combineddf['RoadSection'] = combineddf['Start'] + '-' + combineddf['End']

    outputfolder = create_folder(os.path.join(folder, '..', '3_TableauData'))
    combineddf.to_csv(os.path.join(outputfolder, 'M03A.csv'), index=False)

def freeway(datatype, datelist, Tableau = False, etag = None, keep = False):
    rawdatafolder, mergefolder, excelfolder = freewaydatafolder(datatype=datatype)
    url = "https://tisvcloud.freeway.gov.tw/history/TDCS/" + datatype

    for date in datelist :
        # 1. 下載並解壓縮
        dowloadfilefolder = download_and_extract(url = url, datatype = datatype, date = date, downloadfolder = rawdatafolder, keep = False)

        # 2. 合併
        filelist = findfiles(filefolderpath=dowloadfilefolder, filetype='.csv')
        df = combinefile(filelist=filelist, datatype=datatype)
        mergeoutputfolder = create_folder(os.path.join(mergefolder, date)) # 建立相同日期的資料夾進行處理
        df.to_csv(os.path.join(mergeoutputfolder, f'{date}.csv') , index = False) # 輸出整併過的csv
        delete_folders([dowloadfilefolder]) #回頭刪除解壓縮過的資料

        # # 3. 處理
        df = THI_process(df, datatype=datatype)
        df.to_excel(os.path.join(excelfolder, f'{date}.xlsx'), index = False, sheet_name = date)
    
    if Tableau == True:
        if datatype == 'M03A':
            M03A_Tableau_combined(folder=excelfolder, etag = etag)

    return df

# ===== Step 0: 手動需要調整的參數 =====

# 調整下載的資料區間
starttime = "2025-01-24"
endtime = "2025-01-24"
datelist = getdatelist(endtime,starttime) # 下載的時間區間清單

# ===== Step 1: 選擇需要執行的程式碼 ====

def main():
    '''主要會用freeway這個函數進行三個步驟 (1) 下載 (2) 整併當日資料 (3) 處理
    請根據需要調整datatype(str)

    1. M03A : 主要計算主要路段通過門架的通過量
    2. M05A : 計算通過兩個門架間的速率
    3. M06A : 計算進出匝道進出的數量 (需事先至 "/Input/ETag匝道選擇.xlsx" 進行挑選需要的篩選的進出匝道)
    4. M08A : 計算通過兩個門架之間的OD數量
    '''

    etag = etag_getdf()

    # (1) M03A: 兩行程式碼擇一
    freeway(datatype = 'M03A', datelist = datelist)
    # freeway(datatype = 'M03A', datelist = datelist, keep=False, Tableau = True, etag = etag)  #如果有要轉tableau 的格式則要用這個程式碼

    # (2) M05A: 
    # freeway(datatype = 'M05A', datelist = datelist) 

    # # (3) M06A: 至2_excel 的部分為匝道進出資料，因次要補主縣通過量
    # freeway(datatype = 'M06A', datelist = datelist)
    # try:
    #     filefolderpath = os.path.abspath(os.path.join(os.getcwd(),'..','Output', 'M06A', '1_merge'))
    #     filelist = findfiles(filefolderpath=filefolderpath)
    #     for i in range(len(filelist)): 
    #         filename = os.path.basename(filelist[i])
    #         basename_without_ext = os.path.splitext(filename)[0]  # 去掉副檔名
            
    #         df = pd.read_csv(filelist[i])
    #         df = THI_M06A_step1(df)
    #         df = df.groupby(['DetectionDate', 'DetectionHour', 'GantryID', 'VehicleType'])["index"].nunique().reset_index(name="Volume")
    #         df.to_excel(os.path.join('M06A', '2_excel', f'{basename_without_ext}_主線通過量.xlsx'))
    # except:
    #     pass

    # (4) M08A:
    # freeway(datatype = 'M08A', datelist = datelist)
if __name__ == '__main__':
    main()
