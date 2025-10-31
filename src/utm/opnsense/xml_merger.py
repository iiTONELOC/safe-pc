# type: ignore

import xml.etree.ElementTree as ET
import copy

base = ET.parse("/conf/config.xml")
tmpl = ET.parse("/tmp/safety_config.xml")

base_root = base.getroot()
template_root = tmpl.getroot()

tags_to_replace = [
    "dnsmasq",
    "filter",
    "OPNsense",
]


def merge(dst, src):
    for node in src:

        for tag in tags_to_replace:
            if node.tag == tag:
                old = dst.find(tag)
                if old is not None:
                    dst.remove(old)
                dst.append(copy.deepcopy(node))
                continue

        # system: deep merge, preserve existing, append users
        if node.tag == "system":
            dst_sys = dst.find("system")
            if dst_sys is None:
                dst.append(copy.deepcopy(node))
                continue

            for sys_node in node:
                # handle users
                if sys_node.tag == "user":
                    exists = False

                    for existing in dst_sys.findall("user"):
                        # match by uuid if present
                        if (
                            "uuid" in sys_node.attrib
                            and "uuid" in existing.attrib
                            and sys_node.attrib["uuid"] == existing.attrib["uuid"]
                        ):
                            exists = True
                            break

                        # fallback match by username
                        n1 = sys_node.find("name")
                        n2 = existing.find("name")
                        if n1 is not None and n2 is not None:
                            if n1.text == n2.text:
                                exists = True
                                break

                    if not exists:
                        dst_sys.append(copy.deepcopy(sys_node))
                    continue

                # non-user: recursively merge if container
                existing = dst_sys.find(sys_node.tag)
                if existing is not None and len(sys_node) > 0:
                    merge(existing, sys_node)
                else:
                    if existing is not None:
                        dst_sys.remove(existing)
                    dst_sys.append(copy.deepcopy(sys_node))

            continue

        # default: uuid match or overwrite
        match = None
        if "uuid" in node.attrib:
            for child in dst.findall(node.tag):
                if "uuid" in child.attrib and child.attrib["uuid"] == node.attrib["uuid"]:
                    match = child
                    break
        else:
            match = dst.find(node.tag)

        if match is None:
            dst.append(copy.deepcopy(node))
        else:
            if len(node) and len(match):
                merge(match, node)
            else:
                dst.remove(match)
                dst.append(copy.deepcopy(node))


if __name__ == "__main__":
    merge(base_root, template_root)
    base.write("/conf/config.xml", encoding="utf-8", xml_declaration=True)
    print("Configuration merged successfully.")
    exit(0)
