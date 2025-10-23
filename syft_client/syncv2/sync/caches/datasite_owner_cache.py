from collections import defaultdict
from uuid import UUID
from pydantic import BaseModel, model_validator
from typing import List, Dict, Set, Tuple
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.events.file_change_event import FileChangeEventNode

"""
There are reasons why we want to support merges right now
Even though we have a single merger, we have multiple writers
If these writers are making writes that are not conflicting, we should support them
"""


class DataSiteOwnerEventCache(BaseModel):
    # we keep a list of heads, which are the latest events for each path
    heads: Set[FileChangeEventNode]
    id2node: Dict[UUID, FileChangeEventNode]
    child_dict: Dict[UUID, List[UUID]] = {}

    @model_validator(mode="before")
    def pre_init(cls, data):
        # Add flag to indicate whether this is a new cache
        if data["is_new_cache"]:
            first_event = FileChangeEventNode.noop_event(is_root=True)
            data["heads"] = {first_event}
            data["id2node"] = {first_event.id: first_event}
            data["child_dict"] = {first_event.id: []}
        return data

    def process_proposed_event(
        self, event: ProposedFileChange
    ) -> Tuple[FileChangeEvent, List[FileChangeEvent]]:
        parent: FileChangeEventNode | None = self.find_node_from_branches_breath_first(
            event.parent_id
        )
        if parent is None:
            raise ValueError("event rejected, parent not found, did you initialize")
        else:
            creates_new_head, event_node = self.add_proposed_event_to_local_cache(
                [parent], event
            )
            if creates_new_head:
                merge_event_nodes: List[FileChangeEventNode] = (
                    self.create_merge_head_events()
                )
                merge_events = [merge_event.event for merge_event in merge_event_nodes]
            else:
                merge_events = []

        return event_node, merge_events

    def empty_merge_event(self):
        return FileChangeEventNode.noop_event(is_root=False, parents=[self.heads])

    def create_merge_head_events(self) -> List[FileChangeEventNode]:
        assert len(self.heads) <= 2, (
            "We are assuming max 2 heads for now, other casers shouldnt happen"
        )
        if len(self.heads) == 1:
            return []

        common_ancestor, branch_event_sets = self.find_common_ancestor_bfs(self.heads)
        file_path_to_heads: Dict[str, List[FileChangeEventNode]] = (
            self._get_file_path_to_head_dict(branch_event_sets)
        )

        merge_events: List[FileChangeEventNode] = []

        # this is what you use as parent for the next merge event
        latest_merge_parents: List[FileChangeEventNode] = self.heads

        # for each file with conflicts, we need to create a merge event
        for file_path, heads_with_file in file_path_to_heads.items():
            # if there are multiple branches editing the same file, we need to find the winning branch and merge
            if len(heads_with_file) > 1:
                winning_branch = self._get_winning_branch_for_file(
                    file_path, branch_event_sets
                )

                file_events_in_winning_branch = [
                    e for e in branch_event_sets[winning_branch] if e.path == file_path
                ]
                last_winning_branch_event_for_file = sorted(
                    file_events_in_winning_branch,
                    key=lambda x: x.event.timestamp,
                )[-1]
                # the last event from the winning branch has the final state we want to use
                merge_event_for_file = FileChangeEventNode(
                    event=FileChangeEvent.for_now(
                        path=file_path,
                        content=last_winning_branch_event_for_file.content,
                        parent_ids=[h.id for h in latest_merge_parents],
                    ),
                    parents=latest_merge_parents,
                )
                merge_events.append(merge_event_for_file)
                latest_merge_parents = [merge_event_for_file]

        if len(merge_events) == 0:
            # if not conflicting, just write an empty Event that merges the heads
            merge_events.append(self.empty_merge_event())

        for merge_event in merge_events:
            self.add_event_node_to_local_cache(merge_event)
        return merge_events

    def _get_winning_branch_for_file(
        self,
        file_path: str,
        branch_event_sets: Dict[FileChangeEventNode, Set[FileChangeEventNode]],
    ) -> FileChangeEventNode:
        # the winning branch is determined by some kind of knock-out system
        # for each event in time sorted events, if you dont have the event in your branch, you are out
        # if one branch is left, you are the winner. Not sure how to describe this better
        all_file_events: List[FileChangeEventNode] = [
            event
            for events in branch_event_sets.values()
            for event in events
            if event.path == file_path
        ]
        file_events_sorted_timestamp = sorted(
            all_file_events, key=lambda x: x.event.timestamp
        )
        candidate_winning_branches = set(self.heads)
        winning_branch: UUID | None = None
        for file_event in file_events_sorted_timestamp:
            # skip if node is not in candidate winning branches
            branches_with_node = set(
                [
                    branch_node
                    for branch_node, branch_event_set in branch_event_sets.items()
                    if file_event in branch_event_set
                ]
            )

            # if this event only exist in branches that are not candidates, skip this event
            if len(branches_with_node.intersection(candidate_winning_branches)) == 0:
                continue

            candidate_winning_branches = set(branches_with_node).intersection(
                candidate_winning_branches
            )
            # if we have one left, we stop
            if len(candidate_winning_branches) == 1:
                winning_branch = candidate_winning_branches.pop()
                return winning_branch

        if winning_branch is None:
            raise ValueError(f"No winning branch found for file {file_path}")

    def _get_file_path_to_head_dict(
        self,
        branch_nodes_from_ancestor: Dict[FileChangeEventNode, Set[FileChangeEventNode]],
    ) -> Dict[str, List[UUID]]:
        file_path_to_head = defaultdict(list)
        for head_node, branch_nodes in branch_nodes_from_ancestor.items():
            for branch_node in branch_nodes:
                if branch_node.path is not None:
                    file_path_to_head[branch_node.path].append(head_node)
        return dict(file_path_to_head)

    def conflicting_heads(self):
        pass
        # 1 find the common ancestor of the heads
        # 2 for each head, find all the events to that common ancestor
        # group them per file

        # for each file, if both branches are changing the event in a different way, we have a conflict.
        # We create a merge event that sets the state to the latest state of the winning branch

    def find_common_ancestor_bfs(
        self, heads: List[FileChangeEventNode]
    ) -> Tuple[
        FileChangeEventNode, Dict[FileChangeEventNode, Set[FileChangeEventNode]]
    ]:
        branch_visited_sets = {head: set() for head in heads}

        # "branches" are all the branches that have this node, we keep track of them
        # so we dont do duplicate work for different branches
        bfs_queue = [{"origin_branches": [head], "node": head} for head in heads]

        while len(bfs_queue) > 0:
            item = bfs_queue.pop(0)
            origin_branches = item["origin_branches"]
            current_node: FileChangeEventNode = item["node"]
            for branch_head_node in origin_branches:
                branch_visited_sets[branch_head_node].add(current_node)

            # if everyone has the node, return the node
            all_branches_intersection = set.intersection(*branch_visited_sets.values())
            if len(all_branches_intersection) > 0:
                return all_branches_intersection.pop(), branch_visited_sets

            next_branches = [
                branch_head_node
                for branch_head_node, branch_visited_set in branch_visited_sets.items()
                if current_node in branch_visited_set
            ]

            for parent_node in current_node.parents:
                bfs_queue.append(
                    {"origin_branches": next_branches, "node": parent_node}
                )

        raise ValueError("No common ancestor found")

    def add_proposed_event_to_local_cache(
        self,
        parents: List[FileChangeEventNode],
        proposed_event: ProposedFileChange,
    ) -> Tuple[bool, FileChangeEventNode]:
        event_node = FileChangeEventNode.from_proposed_filechange(
            proposed_event, parents
        )
        return self.add_event_node_to_local_cache(event_node), event_node

    def add_event_node_to_local_cache(self, event_node: FileChangeEventNode):
        self.id2node[event_node.id] = event_node
        # if parent was in heads, remove it
        creates_new_head = False
        for parent in event_node.parents:
            if parent in self.heads:
                self.heads.remove(parent)
            else:
                creates_new_head = True

        self.heads.add(event_node)
        for parent in event_node.parents:
            self.child_dict[parent.id].append(event_node.id)

        return creates_new_head

    def find_node_from_branches_breath_first(
        self,
        target_node_id: UUID,
    ) -> FileChangeEventNode | None:
        visited = set()
        # breath first
        bfs_queue = list(self.heads)
        while bfs_queue:
            current_node: FileChangeEventNode = bfs_queue.pop(0)
            if current_node.id in visited:
                continue
            if current_node.id == target_node_id:
                return current_node
            visited.add(current_node.id)

            if len(current_node.parent_ids) > 0:
                for parent_node in current_node.parents:
                    bfs_queue.append(parent_node)
        return None

    def get_checkpoint_root(self) -> FileChangeEventNode:
        roots = [x for x in self.id2node.values() if x.is_root]
        if len(roots) != 1:
            raise ValueError("Multiple or no root events found")
        return roots[0]
