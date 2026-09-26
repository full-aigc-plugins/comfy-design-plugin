from typing import Dict, Any, List

class WorkflowConverter:
    def __init__(self, http_client):
        self.http_client = http_client
        self.object_info = {}

    async def init(self):
        self.object_info = await self.http_client.get_object_info()

    def convert(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        output = {}

        # 1. Filter valid nodes
        valid_nodes = []
        for node in workflow.get("nodes", []):
            mode = node.get("mode")
            # 2 = Bypass, 4 = Never
            if mode not in (2, 4):
                valid_nodes.append(node)

        # 2. Map nodes by ID
        node_map = {str(node["id"]): node for node in valid_nodes}

        # 3. Map links
        # links structure: [link_id, origin_id, origin_slot, target_id, target_slot, link_type]
        links_map: Dict[str, List[Any]] = {}
        for link in workflow.get("links", []):
            if not link or len(link) < 6:
                continue
            link_id, origin_id, origin_slot, target_id, target_slot, link_type = link
            link_key = f"{link_id}:{link_type}"
            if link_key not in links_map:
                links_map[link_key] = []
            links_map[link_key].extend([str(origin_id), origin_slot])

        # 4. Process each node
        for node in valid_nodes:
            node_id = str(node["id"])
            inputs = {}
            input_names = []
            no_link = 0

            obj_def = self.object_info.get(node["type"])
            if not obj_def:
                raise ValueError(f"MCP_OBJECT_INFO_NOT_FOUND: {node['type']}")

            obj_input = obj_def.get("input", {})
            required_inputs = obj_input.get("required", {})
            optional_inputs = obj_input.get("optional", {})
            hidden_inputs = obj_input.get("hidden", {})

            input_names.extend(required_inputs.keys())
            input_names.extend(optional_inputs.keys())
            input_names.extend(hidden_inputs.keys())

            node_inputs = node.get("inputs", [])
            node_widgets_values = node.get("widgets_values")

            for input_name in input_names:
                # Find matching input declaration in the node definition
                matched_input = None
                for i_def in node_inputs:
                    if i_def.get("name") == input_name:
                        matched_input = i_def
                        break
                
                if matched_input:
                    if matched_input.get("link") is not None:
                        link_val = matched_input.get("link")
                        link_type = matched_input.get("type")
                        inputs[input_name] = links_map.get(f"{link_val}:{link_type}", [])
                    else:
                        if isinstance(node_widgets_values, list):
                            if no_link < len(node_widgets_values) and node_widgets_values[no_link] == "randomize":
                                no_link += 1
                            if no_link < len(node_widgets_values):
                                inputs[input_name] = node_widgets_values[no_link]
                                no_link += 1
                        elif isinstance(node_widgets_values, dict):
                            inputs[input_name] = node_widgets_values.get(input_name)
            
            # Missing widgets values for undeclared inputs? The JS logic just bounds it within names.

            output[node_id] = {
                "inputs": inputs,
                "class_type": node["type"],
                "_meta": {
                    "title": node.get("title") or node.get("type")
                }
            }

        return output
