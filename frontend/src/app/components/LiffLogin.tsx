// src/components/LiffLogin.tsx

import { useState, useEffect } from 'react';
import { User, Lock, Eye, EyeOff, MessageSquare, LogOut } from 'lucide-react';
import { authApi } from '../lib/api';

export function LiffLogin() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [empNo, setEmpNo] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loggedInEmpNo, setLoggedInEmpNo] = useState('');
  const [liffReady, setLiffReady] = useState(false);

  // ✅ init LIFF ก่อน แล้วค่อยดึง userId ได้
  useEffect(() => {
    const initLiff = async () => {
      try {
        const liff = (window as any).liff;
        if (!liff) return;
        await liff.init({ liffId: import.meta.env.VITE_LIFF_ID });
        setLiffReady(true);
      } catch (e) {
        console.error('LIFF init failed:', e);
      }
    };
    initLiff();
  }, []);

  useEffect(() => {
    const storedEmpNo = localStorage.getItem('employeeNumber');
    const bound = localStorage.getItem('isEmployeeBound') === 'true';
    if (storedEmpNo && bound) {
      setIsLoggedIn(true);
      setLoggedInEmpNo(storedEmpNo);
    }
  }, []);

  const getLineUserId = async (): Promise<string | undefined> => {
    try {
      const liff = (window as any).liff;
      if (!liff || !liffReady || !liff.isLoggedIn?.()) return undefined;
      const profile = await liff.getProfile();
      return profile.userId;
    } catch {
      return undefined;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!empNo || !password) {
      setError('กรุณากรอกข้อมูลให้ครบถ้วน');
      return;
    }

    if (!/^\d+$/.test(empNo)) {
      setError('รหัสพนักงานต้องเป็นตัวเลขเท่านั้น');
      return;
    }

    setLoading(true);
    try {
      const lineUserId = await getLineUserId();
      console.log('lineUserId:', lineUserId);        // ← ดูว่าได้ค่าไหม
      console.log('liffReady:', liffReady);          // ← ดูว่า init เสร็จไหม
      console.log('liff object:', (window as any).liff); // ← ดูว่ามี liff ไหม
      console.log('lineUserId:', lineUserId); // debug — ลบออกได้หลัง verify

      // ถ้าดึง lineUserId ไม่ได้ ให้ login ต่อได้ แต่ binding จะไม่เกิด
      if (!lineUserId) {
        console.warn('lineUserId not available — LIFF อาจยัง init ไม่เสร็จ');
      }

      const result = await authApi.employeeLogin(parseInt(empNo), password, lineUserId);

      localStorage.setItem('employeeNumber', String(result.empNo));
      localStorage.setItem('isEmployeeBound', 'true');

      setIsLoggedIn(true);
      setLoggedInEmpNo(String(result.empNo));
    } catch (err: any) {
      setError(err.message || 'เกิดข้อผิดพลาด กรุณาลองใหม่');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    if (!confirm('ต้องการออกจากระบบใช่ไหม?')) return;

    try {
      await authApi.unbind(parseInt(loggedInEmpNo));
    } catch (_) {
      // silent fail — clear local storage ต่อไป
    } finally {
      localStorage.removeItem('employeeNumber');
      localStorage.removeItem('isEmployeeBound');
      setIsLoggedIn(false);
      setLoggedInEmpNo('');
      setEmpNo('');
      setPassword('');
    }
  };

  if (isLoggedIn) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50 flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-500 to-green-600 rounded-3xl mb-4 shadow-lg">
              <MessageSquare className="w-10 h-10 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-gray-900">Policy Chatbot</h1>
            <p className="text-gray-600 mt-2">เข้าสู่ระบบสำเร็จ</p>
          </div>

          <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-16 h-16 bg-green-100 rounded-full mb-4">
                <User className="w-8 h-8 text-green-600" />
              </div>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">ยินดีต้อนรับ!</h2>
              <p className="text-gray-600">รหัสพนักงาน: {loggedInEmpNo}</p>
            </div>

            <div className="bg-blue-50 rounded-xl border border-blue-100 p-4 mb-6">
              <p className="text-sm text-blue-900 text-center">
                💬 คุณสามารถถามคำถามเกี่ยวกับนโยบายและข้อบังคับของบริษัทได้ใน LINE Chat
              </p>
            </div>

            <button
              onClick={handleLogout}
              className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-4 rounded-xl font-semibold focus:outline-none focus:ring-2 focus:ring-gray-400 focus:ring-offset-2 transition-all flex items-center justify-center gap-2"
            >
              <LogOut className="w-5 h-5" />
              ออกจากระบบ
            </button>
          </div>

          <div className="text-center mt-6">
            <p className="text-sm text-gray-500">🔒 Secured by Employee Database</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-green-50 via-white to-blue-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-green-500 to-green-600 rounded-3xl mb-4 shadow-lg">
            <MessageSquare className="w-10 h-10 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Policy Chatbot</h1>
          <p className="text-gray-600 mt-2">Employee Login</p>
          <div className="flex items-center justify-center gap-2 mt-3">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <p className="text-sm text-green-600 font-medium">LINE LIFF</p>
          </div>
        </div>

        <div className="bg-white rounded-3xl shadow-xl border border-gray-100 p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="empNo" className="block text-sm font-medium text-gray-700 mb-2">
                Employee Number
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="empNo"
                  type="text"
                  inputMode="numeric"
                  value={empNo}
                  onChange={(e) => setEmpNo(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent text-lg"
                />
              </div>
              <p className="text-xs text-gray-500 mt-2">ตัวเลขเท่านั้น</p>
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-11 pr-11 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent text-lg"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-start gap-2">
                <span className="text-red-500 mt-0.5">⚠️</span>
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-green-500 to-green-600 text-white py-4 rounded-xl font-semibold hover:from-green-600 hover:to-green-700 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 transition-all shadow-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  กำลังเข้าสู่ระบบ...
                </span>
              ) : (
                'เข้าสู่ระบบ'
              )}
            </button>
          </form>
        </div>

        <div className="text-center mt-6">
          <p className="text-sm text-gray-500">🔒 Secured by Employee Database</p>
          <p className="text-xs text-gray-400 mt-2">LINE LIFF v2 Integration</p>
        </div>
      </div>
    </div>
  );
}