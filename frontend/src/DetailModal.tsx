import React, { useState } from 'react';
import { TreeNode } from './types';
import './DetailModal.css';

interface Props {
  node: TreeNode;
  onClose: () => void;
}

const DetailModal: React.FC<Props> = ({ node, onClose }) => {
  const entries = Object.entries(node.details);
  const [ocidCopied, setOcidCopied] = useState(false);

  const copyOcid = async () => {
    try {
      await navigator.clipboard.writeText(node.id);
      setOcidCopied(true);
      setTimeout(() => setOcidCopied(false), 2000);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = node.id;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      try { document.execCommand('copy'); setOcidCopied(true); setTimeout(() => setOcidCopied(false), 2000); } catch {}
      document.body.removeChild(ta);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">{node.name}</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <table className="modal-table">
          <tbody>
            <tr>
              <th>Type</th>
              <td>{node.type}</td>
            </tr>
            {node.id.startsWith('ocid1.') && (
              <tr>
                <th>OCID</th>
                <td>
                  <span className="modal-ocid">{node.id}</span>
                  <button
                    className="modal-copy-btn"
                    onClick={copyOcid}
                    title="Copy OCID"
                  >
                    {ocidCopied ? '✓ Copied' : '⎘ Copy'}
                  </button>
                </td>
              </tr>
            )}
            {node.time_created && (
              <tr>
                <th>Created</th>
                <td>{node.time_created}</td>
              </tr>
            )}
            {node.type === 'Compartment' && node.details['backup_total'] && (
              <tr>
                <th>Backups</th>
                <td>
                  <div className="modal-backup-summary">
                    <span className="modal-backup-total">Total: {node.details['backup_total']}</span>
                    <span className={`modal-backup-failed${node.details['backup_failed'] !== '0' ? ' modal-backup-failed-nonzero' : ''}`}>
                      Failed: {node.details['backup_failed'] ?? '0'}
                    </span>
                    {node.details['backup_no_backup'] && (
                      <span className="modal-backup-missing">
                        No backup configured: {node.details['backup_no_backup']}
                      </span>
                    )}
                    {node.details['backup_last_ok'] && (
                      <span className="modal-backup-lastok">Last successful: {node.details['backup_last_ok']}</span>
                    )}
                    {!node.details['backup_last_ok'] && (
                      <span className="modal-backup-never">No successful backups recorded</span>
                    )}
                  </div>
                </td>
              </tr>
            )}
            {entries
              .filter(([k]) => !['backup_total','backup_failed','backup_last_ok','backup_no_backup'].includes(k))
              .map(([k, v]) => (
                <tr key={k}>
                  <th>{k.replace(/_/g, ' ')}</th>
                  <td>{v}</td>
                </tr>
              ))}
            {node.link && (
              <tr>
                <th>Console</th>
                <td>
                  <a href={node.link} target="_blank" rel="noopener noreferrer">
                    Open in OCI ↗
                  </a>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default DetailModal;
