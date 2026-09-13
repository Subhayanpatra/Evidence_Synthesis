import tempfile
import unittest
import zipfile
import io
from pathlib import Path
from unittest.mock import Mock, patch

from parser.supplementary import (
    collect_biostudies_files,
    download_europe_pmc_zip,
    extract_doi_from_pmc_xml,
    extract_pmc_supplementary_material,
    extract_supplementary_links_from_html,
    extract_supplementary_content,
    find_supplementary_files,
    validate_download,
)


class SupplementaryExtractionTests(unittest.TestCase):
    def test_finds_standard_and_filename_based_supplements(self):
        xml = b"""
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <body>
            <supplementary-material>
              <media xlink:href="files/table-s1.xlsx" />
            </supplementary-material>
            <p><ext-link xlink:href="bin/mmc2.pdf">file</ext-link></p>
            <p><ext-link xlink:href="article.pdf">main article</ext-link></p>
          </body>
        </article>
        """

        files = find_supplementary_files(xml)

        self.assertEqual(
            {item["File_Name"] for item in files},
            {"table-s1.xlsx", "mmc2.pdf"},
        )

    def test_removes_duplicate_file_references(self):
        xml = b"""
        <article xmlns:xlink="http://www.w3.org/1999/xlink">
          <body>
            <supplementary-material>
              <media xlink:href="bin/Supplement-1.pdf" />
              <media xlink:href="other/supplement_1.pdf" />
            </supplementary-material>
          </body>
        </article>
        """

        files = find_supplementary_files(xml)

        self.assertEqual(len(files), 1)

    def test_extracts_plain_text(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "supplement.txt"
            path.write_text("Supplementary result", encoding="utf-8")

            content = extract_supplementary_content(path)

        self.assertEqual(content, "Supplementary result")

    def test_extracts_supported_files_inside_zip(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "supplement.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("nested/results.txt", "Result from archive")
                archive.writestr("../unsafe.exe", "ignored")

            content = extract_supplementary_content(path)

        self.assertIn("ARCHIVE FILE: results.txt", content)
        self.assertIn("Result from archive", content)
        self.assertNotIn("unsafe.exe", content)

    def test_extracts_supported_files_inside_nested_zip(self):
        nested_bytes = io.BytesIO()
        with zipfile.ZipFile(nested_bytes, "w") as nested_archive:
            nested_archive.writestr("data/results.csv", "name,value\nresult,42")
            nested_archive.writestr("Fig1_HTML.jpg", b"ordinary article figure")

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "supplement.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("nested/materials.zip", nested_bytes.getvalue())

            content = extract_supplementary_content(path)

        self.assertIn("ARCHIVE FILE: materials.zip", content)
        self.assertIn("ARCHIVE FILE: results.csv", content)
        self.assertIn("result,42", content)
        self.assertNotIn("Fig1_HTML.jpg", content)

    def test_europe_pmc_excludes_normal_article_figures(self):
        package = io.BytesIO()
        with zipfile.ZipFile(package, "w") as archive:
            archive.writestr("134_2024_7618_Fig1_HTML.jpg", b"figure")
            archive.writestr("Fig2_HTML.gif", b"figure")
            archive.writestr("supplementary-data.zip", b"PK supplementary")
            archive.writestr("table-s1.csv", b"result,42")

        response = Mock()
        response.content = package.getvalue()
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response

        files, error = download_europe_pmc_zip(session, "PMC123")

        self.assertIsNone(error)
        self.assertEqual(set(files), {"supplementary-data.zip", "table-s1.csv"})

    def test_records_downloaded_video(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "supplement.mp4"
            path.write_bytes(b"video")

            content = extract_supplementary_content(path)

        self.assertIn("Video supplementary material downloaded successfully", content)
        self.assertIn("supplement.mp4", content)

    def test_html_discovery_keeps_only_pmc_instance_bin_links(self):
        html = """
        <html><body>
          <section class="sm">
            <a href="/articles/instance/123/bin/supplement.docx">Supplement</a>
            <a href="/articles/PMC123/pdf/article.pdf">Main paper</a>
          </section>
        </body></html>
        """

        links = extract_supplementary_links_from_html(
            html,
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        )

        self.assertEqual(len(links), 1)
        self.assertEqual(links[0]["filename"], "supplement.docx")

    def test_rejects_html_challenge_and_invalid_pdf(self):
        with self.assertRaisesRegex(ValueError, "HTML page"):
            validate_download("supplement.docx", b"<!doctype html><html></html>")
        with self.assertRaisesRegex(ValueError, "Invalid PDF signature"):
            validate_download("supplement.pdf", b"not a pdf")

    def test_collects_nested_biostudies_file_paths(self):
        study = {
            "files": [{"path": "root.txt", "type": "file"}],
            "section": {
                "files": [
                    {"path": "nested/supplement.docx", "type": "file"},
                    {"path": "nested", "type": "directory"},
                ]
            },
        }

        files = collect_biostudies_files(study)

        self.assertEqual(files, ["root.txt", "nested/supplement.docx"])

    def test_extracts_publisher_doi_from_project_xml(self):
        xml = b"""
        <article><front><article-meta>
          <article-id pub-id-type="doi">10.1007/s41433-026-04479-x</article-id>
        </article-meta></front></article>
        """

        self.assertEqual(
            extract_doi_from_pmc_xml(xml),
            "10.1007/s41433-026-04479-x",
        )

    @patch("parser.supplementary.download_biostudies_files", return_value=({}, []))
    @patch(
        "parser.supplementary.download_europe_pmc_zip",
        return_value=({}, "Europe PMC did not return a ZIP file"),
    )
    @patch(
        "parser.supplementary.download_pmc_html",
        return_value=(
            "<html><body><h1>Article</h1></body></html>",
            "https://pmc.ncbi.nlm.nih.gov/articles/PMC123/",
        ),
    )
    def test_checkpoints_no_supplement_result(
        self,
        _mock_html,
        _mock_europe_pmc,
        _mock_biostudies,
    ):
        xml = b"<article><body><sec><title>Results</title></sec></body></article>"
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = extract_pmc_supplementary_material(
                "PMC123",
                xml_content=xml,
                download_root=temporary_directory,
            )
            checkpoint = (
                Path(temporary_directory)
                / "PMC123"
                / "extraction_checkpoint.json"
            )

            self.assertTrue(checkpoint.is_file())
            self.assertEqual(
                result["Supplementary_Status"],
                "No supplementary files detected",
            )


if __name__ == "__main__":
    unittest.main()
