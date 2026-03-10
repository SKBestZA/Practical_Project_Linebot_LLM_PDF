import { useState, useEffect } from 'react';
import { Users, Plus, Trash2, Edit2, X, Save, Calendar } from 'lucide-react';
import { employeesApi } from '../lib/api';

interface Employee {
  empno: number;
  title: string;
  fname: string;
  lname: string;
  birthday: string;
  sex: string;
  sdpcode: string;
  sdpname?: string;
  startdate: string;
  enddate?: string;
  workstatus?: string;
  loginstatus?: string;
}

interface Department {
  sdpcode: string;
  sdpname: string;
}

const EMPTY_FORM = {
  empNo: '',
  title: '',
  fname: '',
  lname: '',
  birthday: '',
  sex: 'M',
  sdpCode: '',
  startDate: '',
};

export function Employees() {
  const scpCode = localStorage.getItem('adminScpCode') || '';

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [stats, setStats] = useState<{ totalEmployees: number; byDepartment: { dept: string; count: number }[] }>({
    totalEmployees: 0,
    byDepartment: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await employeesApi.list(scpCode);

      // ✅ เรียง active ขึ้นบนก่อน
      const sorted = (res.data.employees || []).sort((a: Employee, b: Employee) => {
        if (a.loginstatus === 'active' && b.loginstatus !== 'active') return -1;
        if (a.loginstatus !== 'active' && b.loginstatus === 'active') return 1;
        return 0;
      });

      setEmployees(sorted);
      setStats({ totalEmployees: res.data.totalEmployees, byDepartment: res.data.byDepartment });
      setDepartments(res.data.departments || []);
    } catch (e: any) {
      setError(e.message || 'โหลดข้อมูลไม่สำเร็จ');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleOpenAdd = () => {
    setEditing(null);
    setFormData(EMPTY_FORM);
    setShowModal(true);
  };

  const handleOpenEdit = (emp: Employee) => {
    setEditing(emp);
    setFormData({
      empNo: String(emp.empno),
      title: emp.title || '',
      fname: emp.fname || '',
      lname: emp.lname || '',
      birthday: emp.birthday?.slice(0, 10) || '',
      sex: emp.sex || 'M',
      sdpCode: emp.sdpcode,
      startDate: emp.startdate?.slice(0, 10) || '',
    });
    setShowModal(true);
  };

  const handleCloseModal = () => {
    setShowModal(false);
    setEditing(null);
    setFormData(EMPTY_FORM);
    setError('');
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await employeesApi.update(editing.empno, {
          title: formData.title,
          fname: formData.fname,
          lname: formData.lname,
          birthday: formData.birthday,
          sex: formData.sex,
          sdpCode: formData.sdpCode,
        });
      } else {
        await employeesApi.add({
          empNo: parseInt(formData.empNo),
          title: formData.title,
          fname: formData.fname,
          lname: formData.lname,
          birthday: formData.birthday,
          sex: formData.sex,
          sdpCode: formData.sdpCode,
          startDate: formData.startDate,
        });
      }
      handleCloseModal();
      fetchData();
    } catch (e: any) {
      setError(e.message || 'บันทึกไม่สำเร็จ');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (empNo: number) => {
    if (!confirm('ต้องการลบพนักงานคนนี้ใช่ไหม?')) return;
    try {
      await employeesApi.delete(empNo);
      fetchData();
    } catch (e: any) {
      setError(e.message || 'ลบไม่สำเร็จ');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Employee Database</h1>
          <p className="text-gray-600 mt-1">Manage employee data for authentication</p>
        </div>
        <button
          onClick={handleOpenAdd}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Employee
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Users className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Employees</p>
              <p className="text-xl font-bold text-gray-900">{stats.totalEmployees}</p>
            </div>
          </div>
        </div>
        {stats.byDepartment.slice(0, 3).map((d) => (
          <div key={d.dept} className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                <Users className="w-5 h-5 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">{d.dept}</p>
                <p className="text-xl font-bold text-gray-900">{d.count}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-900">
          <strong>Note:</strong> รหัสผ่านพนักงานจะถูกตั้งอัตโนมัติจากวันเกิด (DDMMYYYY)
        </p>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="text-center py-12 text-gray-500">กำลังโหลด...</div>
        ) : employees.length === 0 ? (
          <div className="text-center py-12 text-gray-500">ยังไม่มีพนักงาน</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Name</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Employee No.</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Birth Date</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">Department</th>
                  <th className="text-left px-6 py-3 text-xs font-medium text-gray-600 uppercase">LINE Status</th>
                  <th className="text-right px-6 py-3 text-xs font-medium text-gray-600 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {employees.map((emp) => (
                  <tr key={emp.empno} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
                          <Users className="w-4 h-4 text-gray-600" />
                        </div>
                        <span className="font-medium text-gray-900">{emp.title} {emp.fname} {emp.lname}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">{emp.empno}</td>
                    <td className="px-6 py-4 text-gray-600">
                      {emp.birthday ? new Date(emp.birthday).toLocaleDateString('th-TH') : '-'}
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                        {emp.sdpname || emp.sdpcode}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${emp.loginstatus === 'active'
                        ? 'bg-green-100 text-green-800'
                        : 'bg-red-100 text-red-800'
                        }`}>
                        {emp.loginstatus === 'active' ? 'Linked' : 'Not Linked'}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleOpenEdit(emp)}
                          className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(emp.empno)}
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

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-gray-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">
                {editing ? 'Edit Employee' : 'Add New Employee'}
              </h2>
              <button onClick={handleCloseModal} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {!editing && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Employee No.</label>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={formData.empNo}
                    onChange={(e) => setFormData({ ...formData, empNo: e.target.value.replace(/\D/g, '') })}
                    placeholder="000000"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              )}

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">คำนำหน้า</label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                    placeholder="นาย"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">ชื่อ</label>
                  <input
                    type="text"
                    value={formData.fname}
                    onChange={(e) => setFormData({ ...formData, fname: e.target.value })}
                    placeholder="สมชาย"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">นามสกุล</label>
                  <input
                    type="text"
                    value={formData.lname}
                    onChange={(e) => setFormData({ ...formData, lname: e.target.value })}
                    placeholder="ใจดี"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">วันเกิด</label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="date"
                      value={formData.birthday}
                      onChange={(e) => setFormData({ ...formData, birthday: e.target.value })}
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">เพศ</label>
                  <select
                    value={formData.sex}
                    onChange={(e) => setFormData({ ...formData, sex: e.target.value })}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="M">ชาย</option>
                    <option value="F">หญิง</option>
                    <option value="O">อื่นๆ</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">แผนก</label>
                <select
                  value={formData.sdpCode}
                  onChange={(e) => setFormData({ ...formData, sdpCode: e.target.value })}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">เลือกแผนก</option>
                  {departments.map((d) => (
                    <option key={d.sdpcode} value={d.sdpcode}>{d.sdpname}</option>
                  ))}
                </select>
              </div>

              {!editing && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">วันที่เริ่มงาน</label>
                  <div className="relative">
                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <input
                      type="date"
                      value={formData.startDate}
                      onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                      className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                </div>
              )}

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handleCloseModal}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={
                    saving ||
                    !formData.fname || !formData.lname || !formData.birthday || !formData.sdpCode ||
                    (!editing && (!formData.empNo || !formData.startDate))
                  }
                  className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Save className="w-4 h-4" />
                  {saving ? 'กำลังบันทึก...' : editing ? 'Update' : 'Add'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}