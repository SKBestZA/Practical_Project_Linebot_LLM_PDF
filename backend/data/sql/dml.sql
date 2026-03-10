-- ============================================================
-- 7. DML — Mock Data
-- ============================================================

-- บริษัท
INSERT INTO SetCompany (ScpCode, ScpName) VALUES
    ('CP0001', 'kmitl1'),
    ('CP0002', 'kmitl2')
ON CONFLICT DO NOTHING;

-- แผนก (ScpName ถูก trigger เติมให้อัตโนมัติ)
INSERT INTO SetDepartment (SdpCode, SdpName, ScpCode) VALUES
    ('DP0001', 'IT',        'CP0001'),
    ('DP0002', 'HR',        'CP0001'),
    ('DP0003', 'Finance',   'CP0001'),
    ('DP0004', 'IT',        'CP0002'),
    ('DP0005', 'Marketing', 'CP0002')
ON CONFLICT DO NOTHING;

-- Admin (password = "admin1234")
INSERT INTO Admin (Code, Username, PasswordHash, ScpCode) VALUES
    ('AD0001', 'admin',  crypt('admin1234', gen_salt('bf')), 'CP0001'),
    ('AD0002', 'admin2', crypt('admin1234', gen_salt('bf')), 'CP0002')
ON CONFLICT DO NOTHING;

-- Employee (PasswordHash ถูก trigger ตั้งจากวันเกิด DDMMYYYY อัตโนมัติ)
INSERT INTO Employee (EmpNo, Title, Fname, Lname, Birthday, Sex, WorkStatus, SdpCode, StartDate) VALUES
    (1, 'นาย',    'สมชาย',   'มีสุข',  '1990-05-15', 'M', 'active', 'DP0001', '2020-01-01'),
    (2, 'นางสาว', 'สมหญิง',  'ขยัน',   '1995-08-20', 'F', 'active', 'DP0001', '2021-03-01'),
    (3, 'นาย',    'วิชัย',   'ดีมาก',  '1988-12-10', 'M', 'active', 'DP0002', '2019-06-15'),
    (4, 'นาง',    'มานี',    'สุขใจ',  '1993-03-25', 'F', 'active', 'DP0003', '2022-01-10'),
    (5, 'นาย',    'ประเสริฐ', 'มั่นคง', '1985-07-04', 'M', 'active', 'DP0004', '2018-09-01')
ON CONFLICT DO NOTHING;