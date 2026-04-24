export interface TreeNode {
  id: string;
  name: string;
  type: string;
  link: string | null;
  children: TreeNode[];
  time_created: string | null;
  details: Record<string, string>;
  failed?: boolean;
  no_backup?: boolean;
}

export interface RegionTree {
  region: string;
  children: TreeNode[];
  error: string | null;
}

export interface TreeResponse {
  cached_at: string;
  regions: RegionTree[];
}
