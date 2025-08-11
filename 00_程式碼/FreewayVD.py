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
import gzip
from ProcessBasic import * 

# logfile = os.path.join(os.getcwd(), 'VD_logfile.txt')
logfile = None  # 預設為 None，在 main() 裡設定

def download_VD(url, downloadpath):
    """
    下載指定網址的 XML 檔案到指定位置。

    Args:
        url (str): 要下載的 XML 檔案網址。
        downloadpath (str): 檔案下載後的儲存路徑（包含檔案名稱）。
    """

    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # 檢查 HTTP 狀態碼，如有錯誤則拋出異常

        with open(downloadpath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

    except requests.exceptions.RequestException as e:
        updatelog(file=logfile, text = f"ERROR:下載時發生錯誤, {e}")
    except Exception as e:
        updatelog(file=logfile, text = f"ERROR: 發生錯誤, {e}")

def read_xml(xml_file_path, return_raw=False):
    """
    讀取並解析 XML 檔案。

    Args:
        xml_file_path (str): XML 檔案路徑。
        return_raw (bool): 是否返回原始 XML 內容，預設為 False (返回解析後的 XML 根節點)。

    Returns:
        ElementTree.Element 或 str: 解析後的 XML 根節點，或原始 XML 內容 (若 return_raw=True)。
        None: 如果檔案未找到或解析失敗。
    """
    try:
        with open(xml_file_path, 'r', encoding='utf-8') as f:
            xml_content = f.read()
        
        if return_raw:
            return xml_content  # 返回原始 XML 內容
        
        tree = ET.ElementTree(ET.fromstring(xml_content))
        return tree.getroot()  # 返回解析後的 XML 根節點
    except FileNotFoundError:
        updatelog(file=logfile, text = f"ERROR:未找到{xml_file_path}")
        return None
    except ET.ParseError as e:
        updatelog(file=logfile, text = f"ERROR: 解析 XML 檔案時發生錯誤, {e}")
        return None

def parse_vd_xml(xml_content):
    """
    解析 VD XML 資料並轉換為 DataFrame。

    Args:
        xml_content (str): XML 內容。

    Returns:
        pd.DataFrame: 解析後的 DataFrame。
    """
    namespace = {'ns': 'http://traffic.transportdata.tw/standard/traffic/schema/'}
    root = ET.fromstring(xml_content)

    # 解析全域資訊
    update_time = root.find('ns:UpdateTime', namespace).text
    update_interval = root.find('ns:UpdateInterval', namespace).text
    authority_code = root.find('ns:AuthorityCode', namespace).text

    # 解析 VD 資料
    data = []
    for vd in root.findall('ns:VDs/ns:VD', namespace):
        vdid = vd.find('ns:VDID', namespace).text
        sub_authority_code = vd.find('ns:SubAuthorityCode', namespace).text
        bi_directional = vd.find('ns:BiDirectional', namespace).text
        vd_type = vd.find('ns:VDType', namespace).text
        location_type = vd.find('ns:LocationType', namespace).text
        detection_type = vd.find('ns:DetectionType', namespace).text
        position_lon = vd.find('ns:PositionLon', namespace).text
        position_lat = vd.find('ns:PositionLat', namespace).text
        road_id = vd.find('ns:RoadID', namespace).text
        road_name = vd.find('ns:RoadName', namespace)
        road_name = road_name.text if road_name is not None else ''  # 防止 AttributeError
        road_class = vd.find('ns:RoadClass', namespace)
        road_class = road_class.text if road_class is not None else ''
        location_mile = vd.find('ns:LocationMile', namespace)
        location_mile = location_mile.text if location_mile is not None else ''

        # 解析 RoadSection
        start = vd.find('ns:RoadSection/ns:Start', namespace)
        end = vd.find('ns:RoadSection/ns:End', namespace)
        start_text = start.text if start is not None else ''
        end_text = end.text if end is not None else ''

        # 解析 DetectionLinks
        detection_links = vd.findall('ns:DetectionLinks/ns:DetectionLink', namespace)
        for link in detection_links:
            link_id = link.find('ns:LinkID', namespace).text
            bearing = link.find('ns:Bearing', namespace).text
            road_direction = link.find('ns:RoadDirection', namespace).text
            lane_num = link.find('ns:LaneNum', namespace).text
            actual_lane_num = link.find('ns:ActualLaneNum', namespace).text

            data.append([
                update_time, update_interval, authority_code, vdid, sub_authority_code, bi_directional,
                link_id, bearing, road_direction, lane_num, actual_lane_num, vd_type, location_type,
                detection_type, position_lon, position_lat, road_id, road_name, road_class, start_text, end_text, location_mile
            ])

    # 轉成 DataFrame
    columns = [
        "UpdateTime", "UpdateInterval", "AuthorityCode", "VDID", "SubAuthorityCode", "BiDirectional",
        "LinkID", "Bearing", "RoadDirection", "LaneNum", "ActualLaneNum", "VDType", "LocationType",
        "DetectionType", "PositionLon", "PositionLat", "RoadID", "RoadName", "RoadClass", "Start", "End", "LocationMile"
    ]
    
    return pd.DataFrame(data, columns=columns)

def get_text(element, tag, namespace):
    found = element.find(tag, namespace)
    return found.text if found is not None else None

def parse_vdlive_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # 命名空間
    namespace = {'ns': 'http://traffic.transportdata.tw/standard/traffic/schema/'}

    # 解析全局欄位
    update_time = get_text(root, 'ns:UpdateTime', namespace)
    update_interval = get_text(root, 'ns:UpdateInterval', namespace)
    authority_code = get_text(root, 'ns:AuthorityCode', namespace)

    # 存放資料的列表
    data = []

    # 遍歷 VDLive
    for vd in root.findall(".//ns:VDLive", namespace):
        vdid = get_text(vd, "ns:VDID", namespace)
        status = get_text(vd, "ns:Status", namespace)
        data_collect_time = get_text(vd, "ns:DataCollectTime", namespace)

        for link_flow in vd.findall(".//ns:LinkFlow", namespace):
            link_id = get_text(link_flow, "ns:LinkID", namespace)

            for lane in link_flow.findall(".//ns:Lane", namespace):
                lane_id = get_text(lane, "ns:LaneID", namespace)
                lane_type = get_text(lane, "ns:LaneType", namespace)
                speed = get_text(lane, "ns:Speed", namespace)
                occupancy = get_text(lane, "ns:Occupancy", namespace)

                for vehicle in lane.findall(".//ns:Vehicle", namespace):
                    vehicle_type = get_text(vehicle, "ns:VehicleType", namespace)
                    volume = get_text(vehicle, "ns:Volume", namespace)
                    speed_2 = get_text(vehicle, "ns:Speed", namespace)

                    # 加入記錄
                    data.append([
                        update_time, update_interval, authority_code, vdid, link_id, 
                        lane_id, lane_type, speed, occupancy, vehicle_type, volume, 
                        speed_2, status, data_collect_time
                    ])

    # 建立 DataFrame
    columns = [
        "UpdateTime", "UpdateInterval", "AuthorityCode", "VDID", "LinkID", 
        "LaneID", "LaneType", "Speed", "Occupancy", "VehicleType", "Volume", 
        "SpeedAvg", "Status", "DataCollectTime"
    ]
    df = pd.DataFrame(data, columns=columns)
    return df

def vdlive_preliminary_process(df, vdlist = None):
    df['Volume'] = df['Volume'].astype('int64')
    df['Status'] = df['Status'].astype('int64')
    df = df[(df['Volume'] > 0) & (df['Status'] == 0)]

    if vdlist:
        df = df[df['VDID'].isin(vdlist)]

    return df.reset_index(drop = True)

def VDfolder(datatype = 'VDlive'):
    savelocation = create_folder(os.path.join(os.getcwd(), datatype))
    rawdatafolder = create_folder(os.path.join(savelocation, '0_rawdata'))
    mergefolder = create_folder(os.path.join(savelocation, '1_merge'))
    excelfolder = create_folder(os.path.join(savelocation, '2_excel'))
    return rawdatafolder, mergefolder, excelfolder

# def get_vd():
#     vdfolder = create_folder(os.path.join(os.getcwd(), 'VD'))
#     vdxmlfolder = create_folder(os.path.join(vdfolder, 'xml'))
#     vdpath = os.path.join(os.path.join(vdxmlfolder, 'VD.xml'))
#     download_VD(url = 'https://tisvcloud.freeway.gov.tw/history/motc20/VD.xml', downloadpath = vdpath)
#     VD = read_xml(vdpath, return_raw=True)
#     VD = parse_vd_xml(VD)
#     VD.to_excel(os.path.join(vdfolder, 'VD.xlsx'), index = False, sheet_name= 'VD靜態資料')
#     return VD

def get_vd(date = None):
    vdfolder = create_folder(os.path.join(os.getcwd(), 'VD'))
    vdxmlfolder = create_folder(os.path.join(vdfolder, 'xml'))
    vdpath = os.path.join(os.path.join(vdxmlfolder, 'VD.xml'))

    if date:
        create_folder(os.path.join(vdxmlfolder,date))
        vdpath = os.path.join(vdxmlfolder,date,'VD_0000.xml.gz')
        url = f'https://tisvcloud.freeway.gov.tw/history/motc20/VD/{date}/VD_0000.xml.gz'

        response = requests.get(url)
        if response.status_code == 200:
            with open(vdpath, 'wb') as file:
                file.write(response.content)
            extract_gz(vdpath, create_folder(os.path.join(vdpath, '..', 'temp')))
            vdpath = os.path.abspath(os.path.join(vdpath, '..', 'temp', 'VD_0000.xml'))
        else:
            error_message = f"ERROR: {vdpath} 檔案無法下載，狀態碼: {response.status_code}，回應內容: {response.text}"
    else:
        download_VD(url = 'https://tisvcloud.freeway.gov.tw/history/motc20/VD.xml', downloadpath = vdpath)
    VD = read_xml(vdpath, return_raw=True)
    VD = parse_vd_xml(VD)

    if date:
        outputname = os.path.join(vdfolder, f'VD_{date}.xlsx')
    else:
        outputname = os.path.join(vdfolder, 'VD.xlsx')
    VD.to_excel(outputname, index = False, sheet_name= 'VD靜態資料')
    return VD

def extract_gz(destfile, downloadfolder):
    try:
        # 確保目標資料夾存在
        os.makedirs(downloadfolder, exist_ok=True)
        
        # 取得解壓後的檔名
        extracted_file = os.path.join(downloadfolder, os.path.basename(destfile).replace('.gz', ''))
        
        # 解壓檔案
        with gzip.open(destfile, 'rb') as f_in:
            with open(extracted_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        return extracted_file

    except Exception as e:
        updatelog(file=logfile, text = f"ERROR: 解壓失敗：{e}")
        return None
    
def download_and_extract_VD(url, datatype, date, downloadfolder, keep = False):
    '''針對高公局交通資料庫的格式進行下載'''
    hourlist = [f"{i:02d}" for i in range(24)]
    minutelist = [f"{i:02d}" for i in range(0, 60, 1)]
    downloadfolder = create_folder(os.path.join(downloadfolder, date))
    gzdownloadfolder = create_folder(os.path.join(downloadfolder, '壓縮檔'))
    for hour in hourlist:
        for minute in minutelist:
            # https://tisvcloud.freeway.gov.tw/history/motc20/VD/20241205/VDLive_2315.xml.gz
            downloadurl = f"{url}/{date}/VDLive_{hour}{minute}.xml.gz"
            destfile = os.path.join(gzdownloadfolder, f"VDLive_{hour}{minute}.xml.gz")
            checkfile = os.path.abspath(os.path.join(destfile,'..','..',f"VDLive_{hour}{minute}.xml"))
            check_exist_bool = check_pathexist(checkfile)
            if check_exist_bool:
                updatelog(file=logfile, text = f"WARN: {checkfile} 已經存在，不進行下載")
            else:
                response = requests.get(downloadurl)
                if response.status_code == 200:
                    with open(destfile, 'wb') as file:
                        file.write(response.content)
                        updatelog(file=logfile, text = f"INFO: {destfile} 下載成功")
                    extract_gz(destfile, downloadfolder)
                    updatelog(file=logfile, text = f"INFO: {destfile} 解壓縮成功")
                else:
                    error_message = f"ERROR: {destfile} 檔案無法下載，狀態碼: {response.status_code}，回應內容: {response.text}"
                    updatelog(file=logfile, text=error_message)
                    # updatelog(file=logfile, text = f"ERROR: {destfile} 檔案無法下載")
    os.remove(gzdownloadfolder)
    return downloadfolder

def cleanVD(df):
    df["Direction"] = df["VDID"].str.extract(r"VD-[A-Z0-9]+-([A-Z])-")
    df = df.reindex(columns=['VDID', 'Status','DataCollectTime', 'Direction', 'LaneID', 'Speed', 'Occupancy', 'VehicleType', 'Volume'])
    df.columns = ['vdid', 'status', 'datacollecttime', 'vsrdir', 'vsrid', 'speed', 'laneoccupy', 'carid', 'volume']
    return df 

def VD_volume(df, roadselectlist = None):
    df['UpdateTime'] = pd.to_datetime(df['UpdateTime'] )
    df['Date'] = df['UpdateTime'].dt.strftime('%Y/%m/%d')
    df['Hour'] = df['UpdateTime'].dt.strftime('%H')
    df["Direction"] = df["VDID"].str.extract(r"VD-[A-Z0-9]+-([A-Z])-")
    df = pd.pivot_table(
        df,
        index=['VDID', 'Date', 'Hour', 'Direction'],
        columns='VehicleType',
        values='Volume',
        aggfunc='sum'  # 可依需求改成 'mean', 'max' 等
    ).reset_index()
    df[['L','S','T']] = df[['L','S','T']].fillna(0)
    df = df.groupby(['VDID', 'Date', 'Hour', 'Direction']).agg({'S':'sum', 'T':'sum', 'L':'sum'}).reset_index()
    df = df.rename(columns = {'VDID':'設備代碼',
                              'Date':'日期',
                              'Hour':'小時',
                              'Direction':'車道方向', 
                              'S':'小型車',
                              'T':'聯結車',
                              'L':'大型車'})
    
    if roadselectlist : 
        vd_info_dict = {'N1': '國道1號',
                    'N10': '國道10號',
                    'N1H': '國道1號高架',
                    'N1K': '國道1號',
                    'N2': '國道2號',
                    'N3': '國道3號',
                    'N3A': '國道3號甲',
                    'N3K': '國道3號',
                    'N3N': '國道3號',
                    'N4': '國道4號',
                    'N5': '國道5號',
                    'N6': '國道6號',
                    'N8': '國道8號',
                    'T66': '台66',
                    'T68': '台68',
                    'T72': '台72',
                    'T74': '台74',
                    'T76': '台76',
                    'T78': '台78',
                    'T82': '台82',
                    'T84': '台84',
                    'T86': '台86',
                    'T88': '台88'}
        
        df['國道'] = df['設備代碼'].apply(lambda x: x.split('-')[1])
        df['國道'] = df['國道'].map(vd_info_dict)
        df = df[df['國道'].isin(roadselectlist)]
        df = df.drop(columns = ['國道'])
    
    df['小型車分時PCU'] = df['小型車'] * 1.0
    df['聯結車分時PCU'] = df['聯結車'] * 1.4
    df['大型車分時PCU'] = df['大型車'] * 1.4


    return df 

def calculate_peak_hour(VD_Data):
    # 計算合計分時PCU
    updatelog(file=logfile, text = f"INFO: 計算合計分時PCU")
    VD_Data['合計分時PCU'] = VD_Data['小型車分時PCU'] + VD_Data['大型車分時PCU'] + VD_Data['聯結車分時PCU']

    # 找到每組(設備代碼, 日期)的尖峰時段
    updatelog(file=logfile, text = f"INFO: 找到每組(設備代碼, 日期)的尖峰時段")
    VD_Data['尖峰時段'] = VD_Data.groupby(['設備代碼', '日期'])['合計分時PCU'].transform(max)

    # 標示尖峰小時
    VD_Data['尖峰小時'] = np.where(VD_Data['尖峰時段'] == VD_Data['合計分時PCU'], '*', 'NA')

    # 提取尖峰時段資料
    peak_hour = VD_Data[VD_Data['尖峰小時'] == '*'].reset_index(drop=True)
    peak_hour['尖峰時段'] = peak_hour['小時']
    peak_hour.rename(columns={'合計分時PCU': '尖峰小時PCU'}, inplace=True)

    updatelog(file=logfile, text = f"INFO:  合併 尖峰時段、尖峰小時PCU 兩個欄位")
    # 合併尖峰時段資料
    VD_Data = VD_Data.drop('尖峰時段', axis=1)
    VD_Data = VD_Data.merge(peak_hour[['尖峰時段', '尖峰小時PCU', '設備代碼', '日期']], on=['設備代碼', '日期'], how='left')

    # 彙總資料並計算尖峰率
    agg_columns = ['設備代碼', '日期', '車道方向', '尖峰時段', '尖峰小時PCU']
    VD_Data_Day = VD_Data.groupby(agg_columns)[['小型車', '聯結車', '大型車', '小型車分時PCU', '聯結車分時PCU', '大型車分時PCU', '合計分時PCU']].sum().reset_index()
    
    # 整理欄位順序與名稱
    VD_Data_Day = VD_Data_Day[['設備代碼', '日期', '小型車', '聯結車', '大型車', '小型車分時PCU', '聯結車分時PCU', '大型車分時PCU', '合計分時PCU', '尖峰時段', '尖峰小時PCU']]
    VD_Data_Day.columns = ['設備代碼', '日期', '小型車', '聯結車', '大型車', '小型車全日PCU', '聯結車全日PCU', '大型車全日PCU', '合計全日PCU', '尖峰時段', '尖峰小時PCU']

    # 計算尖峰率
    VD_Data_Day['尖峰率'] = round(VD_Data_Day['尖峰小時PCU'] / VD_Data_Day['合計全日PCU'], 3)

    return VD_Data_Day

def VDlive (datelist , datatype = 'VD_live', vdlist = None, roadselectlist = None):
    '''
    VDlive 函數包含下載、解壓縮、過濾、合併等步驟
    
    Args:
        datelist (list): 要下載的日期清單，以%Y%M%D的形式list組成。
        datatype (str): 檔案下載後的儲存類型
        vdlist (list):需要過濾的清單
    
    '''

    # datatype = 'VD_live'
    url = "https://tisvcloud.freeway.gov.tw/history/motc20/VD/" 
    rawdatafolder, mergefolder, excelfolder = VDfolder(datatype=datatype)
    for date in datelist :
        year = date[:4]
        month = date[4:6]

        updatelog(file=logfile, text = f"INFO: 開始下載{date}的{datatype}檔案")
        # Step1 : 下載
        try:
            dowloadfilefolder = os.path.join(rawdatafolder, date)
            dowloadfilefolder = download_and_extract_VD(url, datatype, date, downloadfolder = rawdatafolder, keep = False)
        except:
            pass

        # Step2 : xml -> csv
        updatelog(file=logfile, text = f"INFO: 開始下載讀取{date}的{datatype}原始xml檔案")
        dowloadfilefolder = os.path.join(rawdatafolder, date)
        delete_folders([os.path.join(dowloadfilefolder,'壓縮檔')])
        updatelog(file=logfile, text = f"INFO: 刪除{date}的{datatype}原始gz壓縮檔案")

        filelist = findfiles(filefolderpath=dowloadfilefolder, filetype='.xml')
        VDlivemergename = os.path.join(mergefolder, f"{date}.csv")
        check_path_exist_bool = check_pathexist(VDlivemergename)
        if check_path_exist_bool == False: # 如果已經有merge過的檔案不重複處理 (怕使用者下載不同時間)
            updatelog(file=logfile, text = f"INFO: 開始讀取{date}的{datatype}xml資料")
            VDLive = []
            for filepath in filelist:
                # filepath = filelist[0]
                updatelog(file=logfile, text = f"INFO: 正在讀取{filepath}的xml資料")
                try:
                    df = parse_vdlive_xml(filepath)
                    df = vdlive_preliminary_process(df, vdlist=vdlist)
                    VDLive.append(df)
                except:
                    updatelog(file=logfile, text = f"ERROR: {filepath}原始xml資料出現失誤")
            VDLive = pd.concat(VDLive, ignore_index=True)
            updatelog(file=logfile, text = f"INFO: {date}dataframe 合併成功")
            VDLive.to_csv(VDlivemergename, index = False)
            updatelog(file=logfile, text = f"INFO: {date}資料存於 {VDlivemergename}")
        else :
            updatelog(file=logfile, text = f"WARN: 資料夾中已將有{date}的合併資料，不進行更新")
            VDLive = pd.read_csv(VDlivemergename)

        VDLiveclean = cleanVD(VDLive)
        updatelog(file=logfile, text = f"INFO: {date}dataframe 轉為五分鐘格式")
        VDlivecleanfolder = create_folder(os.path.join(mergefolder, '符合原本五分鐘格式'))
        VDlivecleanname =  os.path.join(VDlivecleanfolder,f'{date}.csv')
        VDLiveclean.to_csv(VDlivecleanname, index = False)
        updatelog(file=logfile, text = f"INFO: {date}(轉為五分鐘格式) 存於 {VDlivecleanname}")


        # Step3 : 統計每個小時通過Volume
        VDLive = VD_volume(VDLive, roadselectlist)
        updatelog(file=logfile, text = f"INFO: {date}資料進行正規化")
        VDvolumecountfolder = create_folder(os.path.join(excelfolder, '正規化分時PCU',year,month))
        VDexcelname = os.path.join(VDvolumecountfolder, f'{date}.xlsx')
        VDLive.to_excel(VDexcelname, index=False)
        updatelog(file=logfile, text = f"INFO: {date}正規化資料輸出於 {VDexcelname}")
        reformat_excel(VDexcelname)
    
    # Step 4 : 把整個月分進行統計
    lastyear = datetime.now().year - 1
    updatelog(file=logfile, text = f"INFO: 開始整併 {lastyear}年 VD通過量資料")
    VDvolumecountfolder = create_folder(os.path.join(excelfolder, '正規化分時PCU', str(lastyear)))
    
    volume_lastyear = read_combined_dataframe(findfiles(filefolderpath=VDvolumecountfolder, filetype='.xlsx'))
    volumeoutputname = os.path.join(create_folder(os.path.join(excelfolder, '正規化分時PCU', '整合')), f'{lastyear}VD 正規化彙整資料20240413.xlsx')
    volume_lastyear.to_excel(volumeoutputname, index=False)
    updatelog(file=logfile, text = f"INFO: {lastyear}年VD通過量資料輸出：{volumeoutputname}")
    reformat_excel(volumeoutputname)


    # Step 5 : 計算尖峰小時PCU
    updatelog(file=logfile, text = f"INFO: 開使轉換尖峰小時PCU {lastyear}年")
    volume_lastyear = calculate_peak_hour(volume_lastyear)
    volumeoutputname = os.path.join(create_folder(os.path.join(excelfolder, '正規化及尖峰小時')), f'{lastyear}VD 正規化及尖峰小時20240413.xlsx')
    volume_lastyear.to_excel(volumeoutputname, index = False)
    updatelog(file=logfile, text = f"INFO: 尖峰小時PCU資料輸出為: {volumeoutputname}")
    reformat_excel(volumeoutputname)

def main():
    # 0. 定義我們的logfile
    global logfile
    logfile = os.path.join(os.getcwd(), 'VD_logfile.txt')
    refreshlog(file = logfile, day = 1)
    
    # 1. 下載VD靜態資料
    vdtable = get_vd()
    updatetime = str(vdtable['UpdateTime'][0])[:10]
    updatelog(file=logfile, text = f"INFO: 下載最新VD靜態資料, 版本更新時間為:{updatetime}. ")
    reformat_excel(excel_path=os.path.join(os.getcwd(), 'VD', 'VD.xlsx'), allsheet=True)



    # 2. 下載VD Live 資料
    # 2-1 調整下載的資料區間
    starttime = "2024-04-13"
    endtime = "2024-04-14"
    datelist = getdatelist(endtime,starttime) # 下載的時間區間清單
    datelist = ["20250619", "20250621"]

    # 2-2 需要過濾出來的VD清單
    SelectVD = [
        "VD-N10-E-1.765-N-Loop", "VD-N10-W-0.894-M-Loop", "VD-N10-E-17.252-M-Loop", "VD-N10-W-15.352-M-Loop",
        "VD-N10-E-21.502-M-Loop", "VD-N10-W-21.427-M-Loop", "VD-N10-E-23.112-M-Loop", "VD-N10-W-23.112-M-Loop",
        "VD-N10-E-3.466-M-Loop", "VD-N10-W-3.273-M-Loop", "VD-N10-E-31.452-M-Loop", "VD-N10-W-31.452-M-Loop",
        "VD-N10-E-7.080-N-Loop", "VD-N10-W-12.862-N-Loop", "VD-N2-E-0.330-M-LOOP", "VD-N2-W-0.25-N-LOOP",
        "VD-N2-E-16.388-M-RS", "VD-N2-W-16.388-M-RS", "VD-N2-E-19.609-M-LOOP", "VD-N2-W-18.210-N-LOOP",
        "VD-N2-E-4.900-N-LOOP", "VD-N2-W-4.740-N-LOOP", "VD-N2-E-7.895-M-LOOP", "VD-N2-W-7.815-M-RS",
        "VD-N2-E-8.893-N-LOOP", "VD-N2-W-9.320-N-LOOP", "VD-N4-E-0.956-M-RS", "VD-N4-W-0.998-M-LOOP",
        "VD-N4-E-10.160-M-RS", "VD-N4-W-10.200-M-LOOP", "VD-N4-E-13.438-M-LOOP", "VD-N4-W-13.172-M-LOOP",
        "VD-N4-E-6.722-M-RS", "VD-N4-W-5.540-M-RS", "VD-N6-E-0.945-M-RS", "VD-N6-W-2.765-M-RS",
        "VD-N6-E-11.100-M-RS", "VD-N6-W-11.640-M-RS", "VD-N6-E-20.478-M-RS", "VD-N6-W-22.470-M-RS",
        "VD-N6-E-25.934-M-RS", "VD-N6-W-25.516-M-RS", "VD-N6-E-3.060-M-LOOP", "VD-N6-W-3.472-M-LOOP",
        "VD-N6-E-33.951-M-LOOP", "VD-N6-W-31.623-M-RS", "VD-N6-E-36.368-M-LOOP", "VD-N6-W-34.675-M-RS",
        "VD-N8-E-1.312-M-Loop", "VD-N8-W-0.542-M-Loop", "VD-N8-E-14.345-N-Loop", "VD-N8-W-14.155-N-Loop",
        "VD-N8-E-2.190-M-Loop", "VD-N8-W-3.362-M-Loop", "VD-N8-E-6.600-N-Loop", "VD-N8-W-8.073-M-Loop",
        "VD-N8-E-9.773-N-Loop", "VD-N8-W-12.410-M-Loop"
    ]

    # 2-3 需要過濾出來的路線
    # SelectRoad = ['國道1號']

    VDlive(datelist = datelist , datatype = 'VD_live', vdlist = SelectVD)

# 執行 main()
if __name__ == '__main__':
    main()