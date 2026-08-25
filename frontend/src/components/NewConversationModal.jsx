import { useEffect, useState } from 'react';
import Modal from './Modal';
import { api } from '../api';
import { formatModelName } from '../modelNames';
import './NewConversationModal.css';

export default function NewConversationModal({ isOpen, onClose, onConfirm }) {
  const [roles, setRoles] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setIsLoading(true);
    api
      .listRoles()
      .then((rolesData) => {
        setRoles(rolesData);
        setSelectedIds(new Set(rolesData.map((r) => r.id)));
      })
      .catch((err) => console.error('Failed to load roles:', err))
      .finally(() => setIsLoading(false));
  }, [isOpen]);

  const toggleRole = (roleId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(roleId)) {
        next.delete(roleId);
      } else {
        next.add(roleId);
      }
      return next;
    });
  };

  const selectAll = () => setSelectedIds(new Set(roles.map((r) => r.id)));
  const selectNone = () => setSelectedIds(new Set());

  const handleStart = async () => {
    setIsCreating(true);
    try {
      await onConfirm([...selectedIds]);
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Choose Council Members">
      {isLoading ? (
        <div className="picker-empty">Loading...</div>
      ) : roles.length === 0 ? (
        <div className="picker-empty">
          No roles available - add one in Settings first.
        </div>
      ) : (
        <>
          <p className="picker-description">
            Pick who sits on the council for this conversation. This selection is
            fixed for the whole conversation, including follow-up messages.
          </p>

          <div className="picker-actions">
            <button className="picker-link-btn" onClick={selectAll}>
              Select All
            </button>
            <button className="picker-link-btn" onClick={selectNone}>
              Select None
            </button>
          </div>

          <div className="picker-list">
            {roles.map((role) => (
              <label key={role.id} className="picker-item">
                <input
                  type="checkbox"
                  checked={selectedIds.has(role.id)}
                  onChange={() => toggleRole(role.id)}
                />
                <div className="picker-item-content">
                  <span className="picker-item-name">{role.name}</span>
                  <div className="picker-item-badges">
                    <span className="badge badge-model">{formatModelName(role.model)}</span>
                    <span className="badge badge-effort">{role.effort || 'no effort'}</span>
                  </div>
                </div>
              </label>
            ))}
          </div>

          <div className="picker-footer">
            <button
              className="role-btn-primary"
              onClick={handleStart}
              disabled={selectedIds.size === 0 || isCreating}
            >
              {isCreating ? 'Starting...' : 'Start Conversation'}
            </button>
          </div>
        </>
      )}
    </Modal>
  );
}
