import requests
import json
import traceback

# 读取配置
def load_cfg():
    try:
        with open("server.txt","r",encoding="utf-8") as f:
            lines = [i.strip() for i in f.readlines() if i.strip()]
        print("【配置读取成功】")
        return lines
    except Exception as e:
        print(f"【配置读取失败】错误：{str(e)}")
        print(traceback.format_exc())
        return None

def main():
    print("========== NapCat 连通性完整检测工具 ==========\n")
    cfg = load_cfg()
    if not cfg:
        input("按回车退出")
        return

    nap_ip = cfg[4]
    nap_port = cfg[5]
    token = cfg[7]
    base_url = f"http://{nap_ip}:{nap_port}"
    headers = {"Authorization":f"Bearer {token}"}

    # 1. 检测端口是否能连通
    print("1. 正在测试端口连通性...")
    try:
        resp = requests.get(base_url,headers=headers,timeout=3)
        print(f"✅ 端口连通成功 状态码：{resp.status_code}")
    except Exception as e:
        print(f"❌ 端口连通失败")
        print(f"错误详情：{str(e)}")
        print(traceback.format_exc())
        print("======================================")
        input("按回车结束检测")
        return

    # 2. 测试获取消息接口
    print("\n2. 正在拉取消息原始数据...")
    msg_url = f"{base_url}/get_msg_list"
    try:
        res = requests.get(msg_url,headers=headers,timeout=3)
        print(f"请求状态码：{res.status_code}")
        print("【接口原始返回内容】")
        print(res.text)
        print("\n【返回数据类型】",type(res.text))

        # 尝试解析JSON
        try:
            data = json.loads(res.text)
            print("✅ JSON解析成功")
            print("数据结构类型：",type(data))
        except Exception as e:
            print(f"❌ JSON解析失败：{str(e)}")

    except Exception as e:
        print(f"❌ 请求消息接口失败")
        print(f"错误详情：{str(e)}")
        print(traceback.format_exc())

    print("\n========== 检测结束 ==========")
    input("按回车键关闭窗口")

if __name__ == "__main__":
    main()