"""`python -m fafu_auto_sign` 的入口点。"""

import argparse
import sys

from fafu_auto_sign.main import run


def main():
    """主入口点，包含命令行参数解析。"""
    parser = argparse.ArgumentParser(description="FAFU自动签到助手")
    parser.add_argument(
        "--config", "-c",
        default="config.json",
        help="配置文件路径 (默认: config.json)"
    )
    args = parser.parse_args()

    try:
        run(args.config)
    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"程序异常退出: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
