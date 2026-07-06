import unittest

from local_rpa_agent.errors import friendly_error_message


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeHTTPError(Exception):
    def __init__(self, status_code):
        super().__init__("http status error")
        self.response = FakeResponse(status_code)


class ClientErrorTests(unittest.TestCase):
    def test_translates_connection_refused_to_readable_message(self):
        error = OSError("[WinError 10061] 由于目标计算机积极拒绝，无法连接")

        self.assertEqual(
            friendly_error_message(error),
            "无法连接 SaaS 服务，请确认 SaaS 服务已启动，或检查网络和 SaaS 地址是否正确。",
        )

    def test_translates_unauthorized_response_to_rebind_message(self):
        error = FakeHTTPError(401)

        self.assertEqual(friendly_error_message(error), "设备绑定已失效，请重新绑定本地 Agent。")


if __name__ == "__main__":
    unittest.main()
