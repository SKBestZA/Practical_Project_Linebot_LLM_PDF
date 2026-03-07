import { useState, useEffect } from 'react';
import { FileText, Upload, Trash2, Download, Edit2, X, Save } from 'lucide-react';
import { documentsApi, employeesApi } from '../lib/api';

const COMPANY = localStorage.getItem('adminScpCode') || '';

interface PolicyFile {
  name: string;
  size: number;
  lastModified: string;
  department: string;
}

interface Department {
  sdpcode: string;
  sdpname: string;
}

export function Policies() {
  const [policies, setPolicies] = useState<PolicyFile[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingFile, setEditingFile] = useState<PolicyFile | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({ department: 'all' });

  const fetchPolicies = async () => {
    setLoading(true);
    try {
      const res = await documentsApi.list(COMPANY);
      setPolicies(res.files || []);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      const res = await employeesApi.list(COMPANY);
      setDepartments(res.data.departments || []);
    } catch (e: any) {
      console.error('fetch departments error:', e.message);
    }
  };

  useEffect(() => {
    fetchPolicies();
    fetchDepartments();
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setSelectedFile(e.target.files[0]);
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    try {
      await documentsApi.upload(selectedFile, COMPANY, formData.department);
      await fetchPolicies();
      handleCloseModal();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleUpdate = async () => {
    if (!editingFile || !selectedFile) return;
    setUploading(true);
    try {
      await documentsApi.update(selectedFile, COMPANY, editingFile.department, editingFile.name);
      await fetchPolicies();
      handleCloseModal();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (policy: PolicyFile) => {
    if (!confirm(`ลบไฟล์ "${policy.name}" ใช่ไหม?`)) return;
    try {
      await documentsApi.delete(COMPANY, policy.department, policy.name);
      await fetchPolicies();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const handleEdit = (policy: PolicyFile) => {
    setEditingFile(policy);
    setFormData({ department: policy.department });
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditingFile(null);
    setSelectedFile(null);
    setFormData({ department: 'all' });
    setError('');
  };

  const getDeptLabel = (sdpcode: string) => {
    if (sdpcode === 'all') return 'All Employees';
    return departments.find((d) => d.sdpcode === sdpcode)?.sdpname || sdpcode;
  };

  const formatSize = (bytes: number) => `${(bytes / 1024 / 1024).toFixed(1)} MB`;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Policy Documents</h1>
          <p className="text-gray-600 mt-1">Manage and upload policy PDF files</p>
        </div>
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Upload className="w-4 h-4" />
          Upload File
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Policies</p>
              <p className="text-xl font-bold text-gray-900">{policies.length}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Public Access</p>
              <p className="text-xl font-bold text-gray-900">
                {policies.filter((p) => p.department === 'all').length}
              </p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <FileText className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Department Only</p>
              <p className="text-xl font-bold text-gray-900">
                {policies.filter((p) => p.department !== 'all').length}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-500">กำลังโหลด...</div>
        ) : policies.length === 0 ? (
          <div className="p-8 text-center text-gray-500">ยังไม่มีเอกสาร</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Document</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Last Modified</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Size</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Access</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-600 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {policies.map((policy) => (
                  <tr key={policy.name} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-red-100 rounded flex items-center justify-center">
                          <FileText className="w-4 h-4 text-red-600" />
                        </div>
                        <p className="font-medium text-gray-900">{policy.name}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {new Date(policy.lastModified).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-gray-600">{formatSize(policy.size)}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${policy.department === 'all'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-orange-100 text-orange-800'
                        }`}>
                        {getDeptLabel(policy.department)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => documentsApi.download(COMPANY, policy.department, policy.name)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          <Download className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleEdit(policy)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(policy)}
                          className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-gray-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">
                {editingFile ? 'Update Policy' : 'Upload New Policy'}
              </h2>
              <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  {editingFile ? 'Replace PDF File' : 'Select PDF File'}
                </label>
                <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-500 transition-colors">
                  <input type="file" accept=".pdf" onChange={handleFileSelect} className="hidden" id="file-upload" />
                  <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-2">
                    <Upload className="w-8 h-8 text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">Click to upload</span>
                    <span className="text-xs text-gray-500">PDF files only</span>
                  </label>
                </div>
                {selectedFile && (
                  <div className="mt-3 flex items-center gap-2 p-3 bg-blue-50 rounded-lg">
                    <FileText className="w-4 h-4 text-blue-600" />
                    <span className="text-sm text-gray-900 flex-1">{selectedFile.name}</span>
                    <button onClick={() => setSelectedFile(null)} className="text-gray-400 hover:text-gray-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Department</label>
                <select
                  value={formData.department}
                  onChange={(e) => setFormData({ department: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Employees</option>
                  {departments.map((d) => (
                    <option key={d.sdpcode} value={d.sdpcode}>
                      {d.sdpname}
                    </option>
                  ))}
                </select>
              </div>

              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}

              <div className="flex gap-3 pt-4">
                <button
                  onClick={handleCloseModal}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={editingFile ? handleUpdate : handleUpload}
                  disabled={!selectedFile || uploading}
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Save className="w-4 h-4" />
                  {uploading ? 'Saving...' : editingFile ? 'Update' : 'Upload'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}