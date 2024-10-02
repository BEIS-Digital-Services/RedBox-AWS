from typing import Callable

from langgraph.constants import Send

from redbox.models.chain import RedboxState


def build_document_group_send(target: str) -> Callable[[RedboxState], list[Send]]:
    def _group_send(state: RedboxState) -> list[Send]:
        if state.get("documents") is None:
            raise KeyError

        group_send_states: list[RedboxState] = [
            RedboxState(
                request=state["request"],
                text=state.get("text"),
                documents={group_key: state["documents"][group_key]},
                route=state.get("route"),
            )
            for group_key in state["documents"]
        ]
        return [Send(node=target, arg=state) for state in group_send_states]

    return _group_send


def build_document_chunk_send(target: str) -> Callable[[RedboxState], list[Send]]:
    def _chunk_send(state: RedboxState) -> list[Send]:
        if state.get("documents") is None:
            raise KeyError

        chunk_send_states: list[RedboxState] = [
            RedboxState(
                request=state["request"],
                text=state.get("text"),
                documents={group_key: {document_key: state["documents"][group_key][document_key]}},
                route=state.get("route"),
            )
            for group_key in state["documents"]
            for document_key in state["documents"][group_key]
        ]
        return [Send(node=target, arg=state) for state in chunk_send_states]

    return _chunk_send


def build_tool_send(target: str) -> Callable[[RedboxState], list[Send]]:
    def _tool_send(state: RedboxState) -> list[Send]:
        if state.get("tool_calls") is None:
            raise KeyError("No tools in state")

        tool_send_states: list[RedboxState] = [
            RedboxState(
                request=state["request"],
                text=state.get("text"),
                documents=state.get("documents"),
                tool_calls={tool_id: tool_call},
                route=state.get("route"),
            )
            for tool_id, tool_call in state["tool_calls"].items()
        ]
        return [Send(node=target, arg=state) for state in tool_send_states]

    return _tool_send
