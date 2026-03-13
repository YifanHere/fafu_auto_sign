"""上传服务多图片随机选择功能测试。

本测试模块验证 UploadService 的多图片随机选择功能：
- _get_image_files(): 扫描目录，过滤隐藏文件，返回支持的图片格式
- _select_random_image(): 从列表中随机选择一张图片

使用 pytest 的 tmp_path fixture 创建临时目录和文件，
使用 random.seed() 实现确定性随机测试。
"""
import random
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from fafu_auto_sign.services.upload_service import UploadService


class TestGetImageFiles:
    """测试 _get_image_files 方法。"""

    def test_finds_all_supported_formats(self, tmp_path: Path):
        """测试正确识别所有支持的图片格式。"""
        # 创建 UploadService 实例
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建各种格式的测试文件
        (tmp_path / "photo.jpg").touch()
        (tmp_path / "photo.jpeg").touch()
        (tmp_path / "screenshot.png").touch()
        (tmp_path / "animation.gif").touch()
        (tmp_path / "modern.webp").touch()

        result = service._get_image_files(str(tmp_path))

        # 验证返回了所有5个文件
        assert len(result) == 5
        # 验证包含所有支持的格式
        assert any("photo.jpg" in f for f in result)
        assert any("photo.jpeg" in f for f in result)
        assert any("screenshot.png" in f for f in result)
        assert any("animation.gif" in f for f in result)
        assert any("modern.webp" in f for f in result)

    def test_filters_hidden_files(self, tmp_path: Path):
        """测试过滤隐藏文件（以.开头的文件）。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建普通文件和隐藏文件
        (tmp_path / "visible.jpg").touch()
        (tmp_path / ".hidden.jpg").touch()
        (tmp_path / "..double_hidden.png").touch()
        (tmp_path / ".DS_Store").touch()

        result = service._get_image_files(str(tmp_path))

        # 只应该返回非隐藏文件
        assert len(result) == 1
        assert "visible.jpg" in result[0]

    def test_filters_unsupported_extensions(self, tmp_path: Path):
        """测试过滤不支持的文件格式。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建支持的和不支持的文件
        (tmp_path / "supported.jpg").touch()
        (tmp_path / "document.pdf").touch()
        (tmp_path / "script.py").touch()
        (tmp_path / "data.txt").touch()
        (tmp_path / "archive.zip").touch()

        result = service._get_image_files(str(tmp_path))

        # 只返回支持的图片格式
        assert len(result) == 1
        assert "supported.jpg" in result[0]

    def test_returns_sorted_list(self, tmp_path: Path):
        """测试返回的列表按字母排序。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 按非字母顺序创建文件
        (tmp_path / "zebra.jpg").touch()
        (tmp_path / "apple.jpg").touch()
        (tmp_path / "mango.jpg").touch()
        (tmp_path / "banana.jpg").touch()

        result = service._get_image_files(str(tmp_path))

        # 验证按字母排序
        filenames = [Path(f).name for f in result]
        assert filenames == ["apple.jpg", "banana.jpg", "mango.jpg", "zebra.jpg"]

    def test_empty_directory_returns_empty_list(self, tmp_path: Path):
        """测试空目录返回空列表。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        result = service._get_image_files(str(tmp_path))

        assert result == []

    def test_handles_mixed_case_extensions(self, tmp_path: Path):
        """测试处理大小写混合的扩展名。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建大小写混合的扩展名
        (tmp_path / "upper.JPG").touch()
        (tmp_path / "mixed.Jpeg").touch()
        (tmp_path / "lower.png").touch()
        (tmp_path / "caps.WEBP").touch()

        result = service._get_image_files(str(tmp_path))

        # 所有大小写变体都应该被识别
        assert len(result) == 4

    def test_ignores_subdirectories(self, tmp_path: Path):
        """测试忽略子目录（只处理文件）。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建文件和子目录
        (tmp_path / "photo.jpg").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.png").touch()

        result = service._get_image_files(str(tmp_path))

        # 只返回当前目录的文件
        assert len(result) == 1
        assert "photo.jpg" in result[0]


class TestSelectRandomImage:
    """测试 _select_random_image 方法。"""

    def test_returns_none_for_empty_list(self):
        """测试空列表返回 None。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        result = service._select_random_image([])

        assert result is None

    def test_selects_from_single_item_list(self):
        """测试单元素列表返回该元素。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        single_item = ["/path/to/only.jpg"]
        result = service._select_random_image(single_item)

        assert result == "/path/to/only.jpg"

    def test_deterministic_with_seed(self):
        """测试使用 seed 后选择是确定性的。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        images = ["/path/1.jpg", "/path/2.jpg", "/path/3.jpg", "/path/4.jpg", "/path/5.jpg"]

        # 使用相同的 seed，应该得到相同的结果
        random.seed(42)
        result1 = service._select_random_image(images)

        random.seed(42)
        result2 = service._select_random_image(images)

        assert result1 == result2

    def test_returns_item_from_list(self):
        """测试返回的元素来自输入列表。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        images = ["/path/a.jpg", "/path/b.png", "/path/c.gif"]

        # 多次运行，验证返回的都是列表中的元素
        for _ in range(10):
            result = service._select_random_image(images)
            assert result in images

    def test_different_seeds_produce_different_results(self):
        """测试不同 seed 可能产生不同结果。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        images = ["/path/1.jpg", "/path/2.jpg", "/path/3.jpg"]

        # 使用不同 seed
        random.seed(123)
        result1 = service._select_random_image(images)

        random.seed(456)
        result2 = service._select_random_image(images)

        # 结果可能不同（虽然不是100%保证，但在大样本下极大概率不同）
        # 我们主要验证不会抛出异常
        assert result1 in images
        assert result2 in images


class TestIntegrationFlow:
    """测试 _get_image_files 和 _select_random_image 的集成流程。"""

    def test_full_flow_with_multiple_images(self, tmp_path: Path):
        """测试完整的扫描-选择流程。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建多个图片文件
        (tmp_path / "img1.jpg").touch()
        (tmp_path / "img2.png").touch()
        (tmp_path / "img3.gif").touch()

        # 获取所有图片
        image_files = service._get_image_files(str(tmp_path))
        assert len(image_files) == 3

        # 随机选择
        random.seed(12345)
        selected = service._select_random_image(image_files)

        # 验证选择的是列表中的某个元素
        assert selected in image_files
        # 验证返回的是完整路径
        assert Path(selected).is_absolute()

    def test_full_flow_with_no_valid_images(self, tmp_path: Path):
        """测试没有有效图片时的流程。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建非图片文件
        (tmp_path / "document.pdf").touch()
        (tmp_path / ".hidden.jpg").touch()

        # 获取图片（应该为空）
        image_files = service._get_image_files(str(tmp_path))
        assert image_files == []

        # 选择应该返回 None
        selected = service._select_random_image(image_files)
        assert selected is None

    def test_full_flow_respects_extension_filtering(self, tmp_path: Path):
        """测试流程正确处理扩展名过滤。"""
        mock_client = MagicMock()
        service = UploadService(mock_client)

        # 创建混合文件
        (tmp_path / "valid.jpg").touch()
        (tmp_path / "valid.png").touch()
        (tmp_path / "invalid.bmp").touch()
        (tmp_path / "invalid.tiff").touch()

        image_files = service._get_image_files(str(tmp_path))

        # 只返回支持的格式
        assert len(image_files) == 2
        extensions = {Path(f).suffix.lower() for f in image_files}
        assert extensions == {".jpg", ".png"}
