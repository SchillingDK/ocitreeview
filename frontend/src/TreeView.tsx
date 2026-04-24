import React, { useState } from 'react';
import { TreeNode } from './types';
import DetailModal from './DetailModal';
import './TreeView.css';

const TYPE_ICONS: Record<string, string> = {
  Compartment: '📁',
  Group: '📂',
  VCN: '🌐',
  Subnet: '🔗',
  SecurityList: '🛡',
  NSG: '🛡',
  RouteTable: '🗺',
  InternetGateway: '🚪',
  NATGateway: '🔀',
  ServiceGateway: '🔌',
  DRG: '🔁',
  Instance: '🖥',
  BootVolume: '💾',
  BootVolumeBackup: '💿',
  BlockVolume: '🗄',
  BlockVolumeBackup: '💿',
  VolumeGroup: '🗂',
  VolumeGroupBackup: '💿',
  Bucket: '🪣',
  FileSystem: '📂',
  MountTarget: '🔧',
  DBSystem: '🗃',
  DBHome: '🏠',
  Database: '🗃',
  DBBackup: '💿',
  AutonomousDB: '⚡',
  ADBBackup: '💿',
  MySQLDB: '🐬',
  MySQLBackup: '💿',
  LoadBalancer: '⚖️',
  NetworkLoadBalancer: '⚖️',
  OKECluster: '☸️',
  NodePool: '🖧',
  Vault: '🔐',
  Key: '🔑',
  Policy: '📋',
};

const RULE_TYPES = new Set(['NSGRule', 'SecurityListRule']);

function getIcon(type: string): string {
  return TYPE_ICONS[type] ?? '•';
}

function isOcid(id: string): boolean {
  return id.startsWith('ocid1.');
}

interface OcidBadgeProps { ocid: string; }

const OcidBadge: React.FC<OcidBadgeProps> = ({ ocid }) => {
  const [copied, setCopied] = useState(false);

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(ocid);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = ocid;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { document.execCommand('copy'); setCopied(true); setTimeout(() => setCopied(false), 2000); } catch {}
      document.body.removeChild(ta);
    }
  };

  return (
    <span
      className={`tree-ocid-badge${copied ? ' tree-ocid-copied' : ''}`}
      title={copied ? 'Copied!' : `OCID: ${ocid}\nClick to copy`}
      onClick={handleClick}
    >
      {copied ? '✓ copied' : 'OCID'}
    </span>
  );
};

// ── Rule table (NSG / Security List) ─────────────────────────────────────────

type SortCol = 'protocol' | 'endpoint' | 'type' | 'ports' | 'is_stateless' | 'description';
type SortDir = 'asc' | 'desc';
interface SortKey { col: SortCol; dir: SortDir; }

interface RuleTableProps {
  rules: TreeNode[];
  depth: number;
}

interface SortableHeaderProps {
  col: SortCol;
  label: string;
  sortKeys: SortKey[];
  onSort: (col: SortCol, multi: boolean) => void;
}

const SortableHeader: React.FC<SortableHeaderProps> = ({ col, label, sortKeys, onSort }) => {
  const keyIndex = sortKeys.findIndex(k => k.col === col);
  const active = keyIndex >= 0;
  const dir = active ? sortKeys[keyIndex].dir : null;
  const rank = sortKeys.length > 1 && active ? keyIndex + 1 : null;

  return (
    <th
      className={`rule-th-sortable${active ? ' rule-th-active' : ''}`}
      onClick={(e) => onSort(col, e.ctrlKey || e.metaKey)}
      title={`Sort by ${label}${sortKeys.length > 1 ? '\nCtrl+click to add/extend sort' : '\nCtrl+click to add as secondary sort'}`}
    >
      {label}
      <span className="sort-indicator">
        {active
          ? <>{dir === 'asc' ? '▲' : '▼'}{rank ? <sup>{rank}</sup> : null}</>
          : '⇅'}
      </span>
    </th>
  );
};

const getEndpoint = (r: TreeNode) =>
  r.details['source'] ?? r.details['destination'] ?? '';
const getEndpointType = (r: TreeNode) =>
  r.details['source_type'] ?? r.details['destination_type'] ?? '';

function getColValue(r: TreeNode, col: SortCol): string {
  switch (col) {
    case 'protocol':     return r.details['protocol'] ?? '';
    case 'endpoint':     return getEndpoint(r);
    case 'type':         return getEndpointType(r);
    case 'ports':        return r.details['ports'] ?? '';
    case 'is_stateless': return r.details['is_stateless'] ?? '';
    case 'description':  return r.details['description'] ?? '';
  }
}

function sortRules(rows: TreeNode[], sortKeys: SortKey[]): TreeNode[] {
  return [...rows].sort((a, b) => {
    for (const { col, dir } of sortKeys) {
      const cmp = getColValue(a, col).localeCompare(getColValue(b, col));
      if (cmp !== 0) return dir === 'asc' ? cmp : -cmp;
    }
    return 0;
  });
}

const RuleTable: React.FC<RuleTableProps> = ({ rules, depth }) => {
  const ingress = rules.filter(r => r.details['direction'] === 'INGRESS');
  const egress  = rules.filter(r => r.details['direction'] === 'EGRESS');
  const [sortKeys, setSortKeys] = useState<SortKey[]>([{ col: 'endpoint', dir: 'asc' }]);

  const handleSort = (col: SortCol, multi: boolean) => {
    setSortKeys(prev => {
      const idx = prev.findIndex(k => k.col === col);
      if (multi) {
        // Ctrl+click: toggle if already present, append if not
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = { col, dir: updated[idx].dir === 'asc' ? 'desc' : 'asc' };
          return updated;
        }
        return [...prev, { col, dir: 'asc' }];
      } else {
        // Plain click: replace sort with this column (toggle dir if sole key)
        if (prev.length === 1 && prev[0].col === col) {
          return [{ col, dir: prev[0].dir === 'asc' ? 'desc' : 'asc' }];
        }
        return [{ col, dir: 'asc' }];
      }
    });
  };

  const headerProps = (col: SortCol, label: string) => ({
    col, label, sortKeys, onSort: handleSort,
  });

  const renderRows = (rows: TreeNode[]) =>
    sortRules(rows, sortKeys).map(r => (
      <tr key={r.id}>
        <td>{r.details['protocol'] ?? '—'}</td>
        <td>{getEndpoint(r) || '—'}</td>
        <td>{getEndpointType(r) || '—'}</td>
        <td>{r.details['ports'] ?? 'all'}</td>
        <td>{r.details['is_stateless'] === 'True' ? 'yes' : 'no'}</td>
        <td>{r.details['description'] ?? ''}</td>
      </tr>
    ));

  const thead = (endpointLabel: string) => (
    <thead>
      <tr>
        <SortableHeader {...headerProps('protocol', 'Protocol')} />
        <SortableHeader col="endpoint" label={endpointLabel} sortKeys={sortKeys} onSort={handleSort} />
        <SortableHeader {...headerProps('type', 'Type')} />
        <SortableHeader {...headerProps('ports', 'Ports')} />
        <SortableHeader {...headerProps('is_stateless', 'Stateless')} />
        <SortableHeader {...headerProps('description', 'Description')} />
      </tr>
    </thead>
  );

  return (
    <div className="rule-table-wrap" style={{ paddingLeft: `${depth * 16 + 20}px` }}>
      {sortKeys.length > 1 && (
        <div className="sort-summary">
          Sort: {sortKeys.map((k, i) => (
            <span key={k.col} className="sort-summary-key">
              {i > 0 && <span className="sort-summary-sep"> › </span>}
              {k.col === 'endpoint' ? 'Source/Dest' : k.col} {k.dir === 'asc' ? '▲' : '▼'}
              <button className="sort-remove-btn" title="Remove this sort key"
                onClick={() => setSortKeys(prev => prev.filter(s => s.col !== k.col))}>×</button>
            </span>
          ))}
          <button className="sort-clear-btn" onClick={() => setSortKeys([{ col: 'endpoint', dir: 'asc' }])}>
            Reset
          </button>
        </div>
      )}
      {ingress.length > 0 && (
        <>
          <div className="rule-table-heading">← Ingress ({ingress.length})</div>
          <table className="rule-table">
            {thead('Source')}
            <tbody>{renderRows(ingress)}</tbody>
          </table>
        </>
      )}
      {egress.length > 0 && (
        <>
          <div className="rule-table-heading">→ Egress ({egress.length})</div>
          <table className="rule-table">
            {thead('Destination')}
            <tbody>{renderRows(egress)}</tbody>
          </table>
        </>
      )}
    </div>
  );
};

// ── Tree node ─────────────────────────────────────────────────────────────────

interface NodeProps {
  node: TreeNode;
  depth: number;
  onInfo: (node: TreeNode) => void;
}

const TreeNodeItem: React.FC<NodeProps> = ({ node, depth, onInfo }) => {
  const [open, setOpen] = useState(depth < 2);
  const hasChildren = node.children.length > 0;
  const hasDetails = node.time_created || Object.keys(node.details).length > 0 || node.link;
  const isRuleParent = (node.type === 'NSG' || node.type === 'SecurityList')
    && node.children.every(c => RULE_TYPES.has(c.type));

  return (
    <li className="tree-node">
      <div
        className="tree-node-row"
        style={{ paddingLeft: `${depth * 16}px` }}
        onClick={() => hasChildren && setOpen((o) => !o)}
      >
        <span className="tree-toggle">
          {hasChildren ? (open ? '▾' : '▸') : ' '}
        </span>
        <span className="tree-icon">{getIcon(node.type)}</span>
        {node.link ? (
          <a
            className="tree-label tree-link"
            href={node.link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            {node.name}
          </a>
        ) : (
          <span className="tree-label">{node.name}</span>
        )}
        {node.time_created && (
          <span className="tree-date">{node.time_created}</span>
        )}
        <span className="tree-type-badge">{node.type}</span>
        {isOcid(node.id) && <OcidBadge ocid={node.id} />}
        {node.failed && node.type === 'Compartment' && (
          <span className="tree-failed-badge tree-failed-compartment" title="This compartment has failed backups">⚠ backups failed</span>
        )}
        {node.failed && node.type !== 'Compartment' && (
          <span className="tree-failed-badge" title={`Backup state: ${node.details['lifecycle_state'] ?? 'FAILED'}`}>⚠ Failed</span>
        )}
        {node.no_backup && node.type === 'Compartment' && (
          <span className="tree-no-backup-badge tree-no-backup-compartment" title="This compartment has resources with no backups configured">⚠ missing backups</span>
        )}
        {node.no_backup && node.type !== 'Compartment' && (
          <span className="tree-no-backup-badge" title="No backups found for this resource">⚠ No backup</span>
        )}
        {hasDetails && (
          <button
            className="tree-info-btn"
            title="View details"
            onClick={(e) => { e.stopPropagation(); onInfo(node); }}
          >
            ℹ
          </button>
        )}
      </div>
      {hasChildren && open && (
        isRuleParent
          ? <RuleTable rules={node.children} depth={depth} />
          : (
            <ul className="tree-children">
              {node.children.map((child) => (
                <TreeNodeItem key={child.id} node={child} depth={depth + 1} onInfo={onInfo} />
              ))}
            </ul>
          )
      )}
    </li>
  );
};

interface TreeViewProps {
  regionName: string;
  nodes: TreeNode[];
}

const TreeView: React.FC<TreeViewProps> = ({ regionName, nodes }) => {
  const [open, setOpen] = useState(true);
  const [selectedNode, setSelectedNode] = useState<TreeNode | null>(null);

  return (
    <div className="region-tree">
      <div className="region-header" onClick={() => setOpen((o) => !o)}>
        <span className="tree-toggle">{open ? '▾' : '▸'}</span>
        <span className="region-icon">🌍</span>
        <span className="region-name">{regionName}</span>
      </div>
      {open && (
        <ul className="tree-root">
          {nodes.map((node) => (
            <TreeNodeItem key={node.id} node={node} depth={1} onInfo={setSelectedNode} />
          ))}
        </ul>
      )}
      {selectedNode && (
        <DetailModal node={selectedNode} onClose={() => setSelectedNode(null)} />
      )}
    </div>
  );
};

export default TreeView;
