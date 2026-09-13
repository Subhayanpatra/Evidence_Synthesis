import re

from lxml import etree


def clean_text(text):
    if text is None:
        return ""

    text = re.sub(r"\s+", " ", str(text))
    text = text.replace("\xa0", " ")
    return text.strip()


def parse_pmc_xml(xml_data):
    """Parse PMC XML into full text, sections, figures, and tables."""
    if xml_data is None:
        return {
            "Full_Text": "",
            "Sections": {},
            "Figures": [],
            "Tables": [],
        }

    try:
        if isinstance(xml_data, bytes):
            root = etree.fromstring(xml_data)
        else:
            root = etree.fromstring(str(xml_data).encode("utf-8"))
    except Exception:
        return {
            "Full_Text": "",
            "Sections": {},
            "Figures": [],
            "Tables": [],
        }

    sections = {}

    def parse_section(sec, parent_title=None):
        title_nodes = sec.xpath("./title//text()")
        section_title = clean_text(" ".join(title_nodes)) or "Unknown Section"
        final_title = f"{parent_title} > {section_title}" if parent_title else section_title

        paragraphs = []
        for paragraph in sec.xpath("./p"):
            paragraph_text = clean_text(" ".join(paragraph.xpath(".//text()")))
            if paragraph_text:
                paragraphs.append(paragraph_text)

        section_text = clean_text(" ".join(paragraphs))
        if section_text:
            sections[final_title] = section_text

        for child_sec in sec.xpath("./sec"):
            parse_section(child_sec, parent_title=final_title)

    for sec in root.xpath(".//body/sec"):
        parse_section(sec)

    figures = []
    for fig in root.xpath(".//body//fig"):
        caption = clean_text(" ".join(fig.xpath(".//caption//text()")))
        if caption:
            figures.append(caption)

    tables = []
    for table in root.xpath(".//body//table-wrap"):
        caption_nodes = table.xpath(".//caption//text()")
        table_nodes = table.xpath(".//table//text()")
        table_text = clean_text(" ".join(caption_nodes) + " " + " ".join(table_nodes))
        if table_text:
            tables.append(table_text)

    full_text_parts = []
    for section_title, section_text in sections.items():
        full_text_parts.append(f"{section_title.upper()}:\n{section_text}")

    for index, figure_text in enumerate(figures, start=1):
        full_text_parts.append(f"FIGURE {index}:\n{figure_text}")

    for index, table_text in enumerate(tables, start=1):
        full_text_parts.append(f"TABLE {index}:\n{table_text}")

    return {
        "Full_Text": clean_text("\n\n".join(full_text_parts)),
        "Sections": sections,
        "Figures": figures,
        "Tables": tables,
    }
