import { useEffect, useState } from 'react';
import { TrendingUp, MessageSquare, FileText, Users } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { dashboardApi } from '../lib/api';

export function Overview() {
  // ✅ แก้จาก 'adminCode' → 'adminScpCode'
  const scpCode = localStorage.getItem('adminScpCode') || '';

  const [dashboard, setDashboard] = useState<any>(null);
  const [topQueries, setTopQueries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [dash, tq] = await Promise.all([
          dashboardApi.getDashboard(scpCode),
          dashboardApi.getTopQueries(scpCode, 5),
        ]);
        setDashboard(dash.data);
        setTopQueries(tq.data || []);
      } catch (e: any) {
        setError(e.message || 'โหลดข้อมูลไม่สำเร็จ');
      } finally {
        setLoading(false);
      }
    };
    fetchAll();
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">กำลังโหลด...</div>;

  if (error) return (
    <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">{error}</div>
  );

  const stats = [
    { name: 'Total Conversations', value: dashboard?.totalConversations ?? 0, icon: MessageSquare, color: 'bg-blue-500' },
    { name: 'Active Policies', value: dashboard?.activePolicies ?? 0, icon: FileText, color: 'bg-purple-500' },
    { name: 'Weekly Conversations', value: dashboard?.weeklyConversations ?? 0, icon: TrendingUp, color: 'bg-green-500' },
    { name: 'Active Employees', value: dashboard?.activeEmployees ?? 0, icon: Users, color: 'bg-orange-500' },
  ];

  const weeklyData: { day: string; conversations: number }[] = dashboard?.weeklyData || [];
  const policyUsage: { policy: string; queries: number }[] = dashboard?.mostQueriedPolicies || [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Policy Chatbot Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">Monitor your AI-powered policy assistant performance</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.name} className="bg-white rounded-lg border border-gray-200 p-6">
            <div className={`${stat.color} p-3 rounded-lg w-fit`}>
              <stat.icon className="w-6 h-6 text-white" />
            </div>
            <div className="mt-4">
              <p className="text-sm text-gray-600">{stat.name}</p>
              <p className="mt-1 text-2xl font-semibold text-gray-900">{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Charts */}
      {(weeklyData.length > 0 || policyUsage.length > 0) && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {weeklyData.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Weekly Conversations</h2>
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={weeklyData}>
                  <defs>
                    <linearGradient id="colorConv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="day" stroke="#6b7280" fontSize={12} />
                  <YAxis stroke="#6b7280" fontSize={12} />
                  <Tooltip />
                  <Area type="monotone" dataKey="conversations" stroke="#3b82f6" fill="url(#colorConv)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {policyUsage.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Most Queried Policies</h2>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={policyUsage} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis type="number" stroke="#6b7280" fontSize={12} />
                  <YAxis dataKey="policy" type="category" stroke="#6b7280" fontSize={12} width={100} />
                  <Tooltip />
                  <Bar dataKey="queries" fill="#8b5cf6" radius={[0, 8, 8, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}

      {/* Top Queries */}
      {topQueries.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Top Queries</h2>
            <p className="text-sm text-gray-500 mt-1">Most frequently asked questions</p>
          </div>
          <div className="p-6 space-y-4">
            {topQueries.map((item, i) => (
              <div key={i}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900">{item.topic}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-900">{item.count}</span>
                    <span className="text-sm text-gray-500">({item.percentage?.toFixed(1)}%)</span>
                  </div>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${item.percentage}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {topQueries.length === 0 && weeklyData.length === 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center text-gray-500">
          ยังไม่มีข้อมูลการใช้งาน
        </div>
      )}
    </div>
  );
}