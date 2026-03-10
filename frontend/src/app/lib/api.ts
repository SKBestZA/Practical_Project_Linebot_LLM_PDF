// src/lib/api.ts

const BASE_URL = import.meta.env.VITE_API_URL;

function getToken(): string | null {
    return localStorage.getItem('adminToken');
}

async function request<T>(
    path: string,
    options: RequestInit = {}
): Promise<T> {
    const token = getToken();

    const res = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...options.headers,
        },
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
        if (res.status === 401) {
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminCode');
            localStorage.removeItem('adminUsername');
            localStorage.removeItem('adminScpName');
            localStorage.removeItem('adminScpCode');
            window.location.href = '/login';
        }
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    return res.json();
}

// ─── Auth ────────────────────────────────────────
export const authApi = {
    adminLogin: (username: string, password: string) =>
        request<{
            status: string;
            message: string;
            adminCode: string;
            username: string;
            token: string;
            scpName: string;
            scpCode: string;
        }>(
            '/auth/admin/login',
            { method: 'POST', body: JSON.stringify({ username, password }) }
        ),

    adminLogout: () =>
        request('/auth/admin/logout', { method: 'POST' }),

    checkLine: (lineUserId: string) =>
        request<{ status: string; isBound: boolean; empNo: number | null; fullName: string | null; liffUrl: string | null }>(
            '/auth/check-line',
            { method: 'POST', body: JSON.stringify({ lineUserId }) }
        ),

    employeeLogin: (empNo: number, password: string, lineUserId?: string) =>
        request<{ status: string; message: string; empNo: number }>(
            '/auth/login',
            { method: 'POST', body: JSON.stringify({ empNo, password, lineUserId }) }
        ),

    unbind: (empNo: number) =>
        request('/auth/unbind', { method: 'POST', body: JSON.stringify({ empNo }) }),
};

// ─── Dashboard ───────────────────────────────────
export const dashboardApi = {
    getDashboard: (scpCode: string) =>
        request<{ status: string; data: { totalConversations: number; activePolicies: number; weeklyConversations: number; mostQueriedPolicies: { docId: string; count: number }[] } }>(
            `/admin/dashboard?scpCode=${scpCode}`
        ),

    getTopQueries: (scpCode: string, limit = 10) =>
        request<{ status: string; data: { topic: string; count: number; percentage: number }[] }>(
            `/admin/top-queries?scpCode=${scpCode}&limit=${limit}`
        ),
};

// ─── Documents ───────────────────────────────────
export const documentsApi = {
    list: (companyCode: string, department = 'all') =>
        request<{ status: string; total: number; files: { name: string; size: number; lastModified: string; department: string }[] }>(
            `/documents/list?company_code=${companyCode}&department=${department}`
        ),

    upload: (file: File, companyCode: string, department: string) => {
        const token = getToken();
        const formData = new FormData();
        formData.append('file', file);
        return fetch(`${BASE_URL}/documents/upload?company_code=${companyCode}&department=${department}`, {
            method: 'POST',
            headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
            body: formData,
        }).then(async (res) => {
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            return res.json();
        });
    },

    update: (file: File, companyCode: string, department: string, oldFilename: string) => {
        const token = getToken();
        const formData = new FormData();
        formData.append('file', file);
        return fetch(
            `${BASE_URL}/documents/update?company_code=${companyCode}&department=${department}&old_filename=${encodeURIComponent(oldFilename)}`,
            {
                method: 'PUT',
                headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
                body: formData,
            }
        ).then(async (res) => {
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
                throw new Error(err.detail || `HTTP ${res.status}`);
            }
            return res.json();
        });
    },

    delete: (companyCode: string, department: string, filename: string) =>
        request(`/documents/delete?company_code=${companyCode}&department=${department}&filename=${encodeURIComponent(filename)}`, {
            method: 'DELETE',
        }),

    download: async (companyCode: string, department: string, filename: string) => {
        const token = getToken();
        const res = await fetch(
            `${BASE_URL}/documents/download?company_code=${companyCode}&department=${department}&filename=${encodeURIComponent(filename)}`,
            { headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) } }
        );
        if (!res.ok) throw new Error('ดาวน์โหลดไม่สำเร็จ');
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    },
};

// ─── Employees ───────────────────────────────────
export const employeesApi = {
    list: (scpCode: string) =>
        request<{ status: string; data: { totalEmployees: number; byDepartment: { dept: string; count: number }[]; departments: { sdpcode: string; sdpname: string }[]; employees: any[] } }>(
            `/admin/employees?scpCode=${scpCode}`
        ),

    add: (data: {
        empNo: number;
        title: string;  // ✅ คำนำหน้า
        fname: string;  // ✅ ชื่อจริง
        lname: string;
        birthday: string;
        sex: string;
        sdpCode: string;
        startDate: string;
    }) =>
        request('/admin/employees', { method: 'POST', body: JSON.stringify(data) }),

    update: (empNo: number, data: Partial<{
        title: string;  // ✅ คำนำหน้า
        fname: string;  // ✅ ชื่อจริง
        lname: string;
        birthday: string;
        sex: string;
        sdpCode: string;
        endDate: string;
    }>) =>
        request(`/admin/employees/${empNo}`, { method: 'PUT', body: JSON.stringify(data) }),

    delete: (empNo: number) =>
        request(`/admin/employees/${empNo}`, { method: 'DELETE' }),
};

// ─── Settings ────────────────────────────────────
export const settingsApi = {
    changePassword: (adminCode: string, currentPassword: string, newPassword: string) =>
        request('/admin/password', {
            method: 'PUT',
            body: JSON.stringify({ adminCode, currentPassword, newPassword }),
        }),
};