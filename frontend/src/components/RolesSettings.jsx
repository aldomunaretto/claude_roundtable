import { useEffect, useState } from 'react';
import Modal from './Modal';
import { api } from '../api';
import { formatModelName } from '../modelNames';
import './RolesSettings.css';

const EFFORT_OPTIONS = ['low', 'medium', 'high', 'xhigh', 'max'];

const emptyForm = { name: '', system_prompt: '', model: '', effort: 'high' };

export default function RolesSettings({ isOpen, onClose }) {
  const [roles, setRoles] = useState([]);
  const [models, setModels] = useState([]);
  const [modelsFetchFailed, setModelsFetchFailed] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [editingRoleId, setEditingRoleId] = useState(null); // null | 'new' | role id
  const [formState, setFormState] = useState(emptyForm);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState(null);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [rolesData, modelsData] = await Promise.all([
        api.listRoles(),
        api.listModels().catch(() => {
          setModelsFetchFailed(true);
          return [];
        }),
      ]);
      setRoles(rolesData);
      setModels(modelsData);
    } catch (err) {
      console.error('Failed to load roles settings:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      setEditingRoleId(null);
      setError(null);
      loadData();
    }
  }, [isOpen]);

  const startAdd = () => {
    setFormState({
      ...emptyForm,
      model: models[0]?.id || 'claude-opus-5',
    });
    setError(null);
    setEditingRoleId('new');
  };

  const startEdit = (role) => {
    setFormState({
      name: role.name,
      system_prompt: role.system_prompt,
      model: role.model,
      effort: role.effort || '',
    });
    setError(null);
    setEditingRoleId(role.id);
  };

  const cancelEdit = () => {
    setEditingRoleId(null);
    setError(null);
  };

  const handleDelete = (role) => {
    if (!window.confirm(`Delete "${role.name}" from the roster? This cannot be undone.`)) {
      return;
    }
    api
      .deleteRole(role.id)
      .then(() => setRoles((prev) => prev.filter((r) => r.id !== role.id)))
      .catch((err) => console.error('Failed to delete role:', err));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formState.name.trim() || !formState.system_prompt.trim() || !formState.model.trim()) {
      setError('Name, system prompt, and model are all required.');
      return;
    }

    setIsSaving(true);
    setError(null);
    const payload = {
      name: formState.name.trim(),
      system_prompt: formState.system_prompt,
      model: formState.model.trim(),
      effort: formState.effort || null,
    };

    try {
      if (editingRoleId === 'new') {
        await api.createRole(payload);
      } else {
        await api.updateRole(editingRoleId, payload);
      }
      const rolesData = await api.listRoles();
      setRoles(rolesData);
      setEditingRoleId(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Council Settings">
      {isLoading ? (
        <div className="roles-empty">Loading...</div>
      ) : editingRoleId !== null ? (
        <form className="role-form" onSubmit={handleSave}>
          <label>
            Name
            <input
              type="text"
              value={formState.name}
              onChange={(e) => setFormState({ ...formState, name: e.target.value })}
              placeholder="e.g. The Skeptic"
            />
          </label>

          <label>
            System Prompt
            <textarea
              value={formState.system_prompt}
              onChange={(e) => setFormState({ ...formState, system_prompt: e.target.value })}
              rows={5}
              placeholder="Describe this advisor's thinking style..."
            />
          </label>

          <label>
            Model
            {modelsFetchFailed || models.length === 0 ? (
              <input
                type="text"
                value={formState.model}
                onChange={(e) => setFormState({ ...formState, model: e.target.value })}
                placeholder="claude-opus-5"
              />
            ) : (
              <select
                value={formState.model}
                onChange={(e) => setFormState({ ...formState, model: e.target.value })}
              >
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            )}
          </label>

          <label>
            Effort
            <select
              value={formState.effort}
              onChange={(e) => setFormState({ ...formState, effort: e.target.value })}
            >
              <option value="">(no effort parameter)</option>
              {EFFORT_OPTIONS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </label>

          {error && <div className="role-form-error">{error}</div>}

          <div className="role-form-actions">
            <button type="button" className="role-btn-secondary" onClick={cancelEdit} disabled={isSaving}>
              Cancel
            </button>
            <button type="submit" className="role-btn-primary" disabled={isSaving}>
              {isSaving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      ) : (
        <>
          <button className="role-btn-primary add-member-btn" onClick={startAdd}>
            + Add Member
          </button>

          {roles.length === 0 ? (
            <div className="roles-empty">
              No council members yet - add one to get started.
            </div>
          ) : (
            <div className="roles-list">
              {roles.map((role) => (
                <div key={role.id} className="role-card">
                  <div className="role-card-header">
                    <span className="role-name">{role.name}</span>
                    {role.is_default && <span className="badge badge-default">Default</span>}
                  </div>
                  <div className="role-card-badges">
                    <span className="badge badge-model">{formatModelName(role.model)}</span>
                    <span className="badge badge-effort">{role.effort || 'no effort'}</span>
                  </div>
                  <p className="role-prompt-preview">{role.system_prompt}</p>
                  <div className="role-card-actions">
                    <button className="role-btn-secondary" onClick={() => startEdit(role)}>
                      Edit
                    </button>
                    <button className="role-btn-danger" onClick={() => handleDelete(role)}>
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Modal>
  );
}
