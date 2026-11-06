import ipaddress
import os
import tempfile
import unittest

from phone_finder import find_phone, load_cached, save_cached

NETWORK = ipaddress.ip_network("10.27.72.0/22")


class FindPhoneTest(unittest.TestCase):
    def setUp(self):
        self.checked = []

    def is_open(self, open_hosts):
        def check(ip):
            self.checked.append(ip)
            return ip in open_hosts
        return check

    def test_前回のIPがつながればすぐ返す(self):
        ip = find_phone(NETWORK, "10.27.74.56", self.is_open({"10.27.74.56"}), lambda ip: True)
        self.assertEqual(ip, "10.27.74.56")
        self.assertEqual(self.checked, ["10.27.74.56"])

    def test_前回のIPがだめならネットワークから探す(self):
        ip = find_phone(NETWORK, "10.27.72.79", self.is_open({"10.27.75.9"}), lambda ip: True)
        self.assertEqual(ip, "10.27.75.9")

    def test_前回のIPがなければ探す(self):
        self.assertEqual(find_phone(NETWORK, None, self.is_open({"10.27.73.1"}), lambda ip: True), "10.27.73.1")

    def test_ポートが開いていても招き猫のスマホでなければ選ばない(self):
        ip = find_phone(NETWORK, None, self.is_open({"10.27.72.5", "10.27.74.56"}), lambda ip: ip == "10.27.74.56")
        self.assertEqual(ip, "10.27.74.56")

    def test_前回のIPが別の機器になっていたら探し直す(self):
        ip = find_phone(NETWORK, "10.27.72.5", self.is_open({"10.27.72.5", "10.27.74.56"}),
                        lambda ip: ip == "10.27.74.56")
        self.assertEqual(ip, "10.27.74.56")

    def test_自分のIPは調べない(self):
        find_phone(NETWORK, None, self.is_open(set()), lambda ip: True, own="10.27.74.160")
        self.assertNotIn("10.27.74.160", self.checked)
        self.assertEqual(len(self.checked), NETWORK.num_addresses - 3)

    def test_見つからなければNone(self):
        self.assertIsNone(find_phone(NETWORK, None, self.is_open(set()), lambda ip: True))


class CacheTest(unittest.TestCase):
    def test_保存したIPを読める(self):
        path = os.path.join(tempfile.mkdtemp(), "phone_ip")
        self.assertIsNone(load_cached(path))
        save_cached(path, "10.27.74.56")
        self.assertEqual(load_cached(path), "10.27.74.56")


if __name__ == "__main__":
    unittest.main()
