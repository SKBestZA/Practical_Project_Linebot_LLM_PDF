-- ============================================================
-- SAFE RESET
-- ============================================================
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'employee') THEN
        DROP TRIGGER IF EXISTS setEmployeeBirthday ON Employee;
        DROP TRIGGER IF EXISTS setEmployeeWorkStatus ON Employee;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'setdepartment') THEN
        DROP TRIGGER IF EXISTS fillDeptCompanyName ON SetDepartment;
        DROP TRIGGER IF EXISTS syncCompanyNameToDept ON SetDepartment;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'setcompany') THEN
        DROP TRIGGER IF EXISTS syncCompanyNameToDept ON SetCompany;
    END IF;
END $$;

DROP FUNCTION IF EXISTS fnAdminLogin(VARCHAR, TEXT);
DROP FUNCTION IF EXISTS fnAdminChangePassword(CHAR, TEXT, TEXT);
DROP FUNCTION IF EXISTS fnEmployeeLogin(INT, TEXT, VARCHAR);
DROP FUNCTION IF EXISTS fnCheckLineUser(VARCHAR);
DROP FUNCTION IF EXISTS trgEmployeeBirthday();
DROP FUNCTION IF EXISTS trgFillDeptCompanyName();
DROP FUNCTION IF EXISTS trgEmployeeWorkStatus();
DROP FUNCTION IF EXISTS fnAdminChangePassword();

DROP TABLE IF EXISTS QueryDetail CASCADE;
DROP TABLE IF EXISTS QueryLog CASCADE;
DROP TABLE IF EXISTS Document CASCADE;
DROP TABLE IF EXISTS Admin CASCADE;
DROP TABLE IF EXISTS Employee CASCADE;
DROP TABLE IF EXISTS SetDepartment CASCADE;
DROP TABLE IF EXISTS SetCompany CASCADE;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ============================================================
-- 1. โครงสร้างองค์กร
-- ============================================================
CREATE TABLE SetCompany (
    ScpCode  CHAR(6)      PRIMARY KEY,
    ScpName  VARCHAR(20)  NOT NULL
);

CREATE TABLE SetDepartment (
    SdpCode  CHAR(6)      PRIMARY KEY,
    SdpName  VARCHAR(20)  NOT NULL,
    ScpCode  CHAR(6)      NOT NULL  REFERENCES SetCompany(ScpCode),
    ScpName  VARCHAR(20)  NOT NULL
);

-- ============================================================
-- 2. พนักงาน
-- ============================================================
CREATE TABLE Employee (
    EmpNo           INT          PRIMARY KEY,
    Title           VARCHAR(20)  NOT NULL,
    Fname           VARCHAR(20)  NOT NULL,
    Lname           VARCHAR(20)  NOT NULL,
    Birthday        DATE,
    Sex             CHAR(1)      CHECK (Sex IN ('M','F','O')),
    Age             INT,
    WorkStatus      VARCHAR(10),
    SdpCode         CHAR(6)      NOT NULL  REFERENCES SetDepartment(SdpCode),
    StartDate       DATE         NOT NULL,
    EndDate         DATE,
    PasswordHash    CHAR(60)     NOT NULL,
    LineUserID      VARCHAR(33)  UNIQUE,
    IsBound         BOOLEAN      NOT NULL  DEFAULT FALSE,
    LoginDate       TIMESTAMPTZ,
    LoginExpireDate DATE,
    LoginStatus     VARCHAR(10)
);

-- ============================================================
-- 3. Admin — อ้าง ScpCode (company) โดยตรง
-- ============================================================
CREATE TABLE Admin (
    Code         CHAR(6)      PRIMARY KEY,
    Username     VARCHAR(20)  NOT NULL  UNIQUE,
    PasswordHash CHAR(60)     NOT NULL,
    ScpCode      CHAR(6)      NOT NULL  REFERENCES SetCompany(ScpCode),
    Token        CHAR(36),
    ExpireDate   DATE,
    LoginDate    TIMESTAMPTZ,
    LoginStatus  VARCHAR(10)
);

-- ============================================================
-- 4. เอกสารและ Query Log
-- ============================================================

-- SdpCode = NULL หมายถึงทุกแผนกในบริษัทนั้น
CREATE TABLE Document (
    DocID     CHAR(6)      PRIMARY KEY,
    Name      VARCHAR(50)  NOT NULL,
    LastDate  DATE,
    AdminCode CHAR(6)      NOT NULL  REFERENCES Admin(Code),
    ScpCode   CHAR(6)      NOT NULL  REFERENCES SetCompany(ScpCode),
    SdpCode   CHAR(6)                REFERENCES SetDepartment(SdpCode)  -- NULL = ทุกแผนก
);

CREATE TABLE QueryLog (
    QueryID   BIGSERIAL    PRIMARY KEY,
    EmpNo     INT          NOT NULL  REFERENCES Employee(EmpNo),
    Topic     VARCHAR(255),
    Type      VARCHAR(10)  NOT NULL  DEFAULT 'query'  CHECK (Type IN ('query', 'blocked')),  -- ✅ เพิ่ม
    TimeStamp TIMESTAMPTZ  NOT NULL  DEFAULT NOW()
);

CREATE TABLE QueryDetail (
    QueryID  BIGINT    NOT NULL  REFERENCES QueryLog(QueryID),
    Seq      INT       NOT NULL,
    Page     VARCHAR(100),
    DocID    CHAR(6)   REFERENCES Document(DocID),
    PRIMARY KEY (QueryID, Seq)
);

-- ============================================================
-- 5. TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION trgEmployeeBirthday() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.Birthday IS NOT NULL THEN
        NEW.Age := DATE_PART('year', AGE(CURRENT_DATE, NEW.Birthday))::INT;
        IF TG_OP = 'INSERT' OR NEW.Birthday IS DISTINCT FROM OLD.Birthday THEN
            NEW.PasswordHash := crypt(TO_CHAR(NEW.Birthday, 'DDMMYYYY'), gen_salt('bf'));
        END IF;
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER setEmployeeBirthday
BEFORE INSERT OR UPDATE OF Birthday ON Employee
FOR EACH ROW EXECUTE FUNCTION trgEmployeeBirthday();

CREATE OR REPLACE FUNCTION trgEmployeeWorkStatus() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.EndDate IS NOT NULL AND NEW.EndDate <= CURRENT_DATE THEN
        NEW.WorkStatus := 'inactive';
    ELSE
        NEW.WorkStatus := 'active';
    END IF;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER setEmployeeWorkStatus
BEFORE INSERT OR UPDATE OF EndDate ON Employee
FOR EACH ROW EXECUTE FUNCTION trgEmployeeWorkStatus();

CREATE OR REPLACE FUNCTION trgFillDeptCompanyName() RETURNS TRIGGER AS $$
BEGIN
    SELECT ScpName INTO NEW.ScpName FROM SetCompany WHERE ScpCode = NEW.ScpCode;
    RETURN NEW;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER fillDeptCompanyName
BEFORE INSERT OR UPDATE OF ScpCode ON SetDepartment
FOR EACH ROW EXECUTE FUNCTION trgFillDeptCompanyName();

-- ============================================================
-- 6. API FUNCTIONS
-- ============================================================

-- ✅ เปลี่ยน res_Name → res_Title ให้ตรงกับ column จริงใน Employee
CREATE OR REPLACE FUNCTION fnCheckLineUser(pLineUserID VARCHAR(33))
RETURNS TABLE (
    res_IsBound  BOOLEAN,
    res_EmpNo    INT,
    res_Title    VARCHAR(20),  -- ✅ แก้จาก res_Name
    res_Fname    VARCHAR(20),
    res_Lname    VARCHAR(20)
)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    vEmp Employee%ROWTYPE;
BEGIN
    SELECT * INTO vEmp
    FROM Employee e
    WHERE e.LineUserID      = pLineUserID
      AND e.IsBound         = TRUE
      AND e.LoginStatus     = 'active'
      AND (e.LoginExpireDate IS NULL OR e.LoginExpireDate >= CURRENT_DATE);

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, NULL::INT,
                            NULL::VARCHAR(20), NULL::VARCHAR(20), NULL::VARCHAR(20);
        RETURN;
    END IF;

    -- ✅ ส่ง Title แทน Name
    RETURN QUERY SELECT TRUE, vEmp.EmpNo, vEmp.Title, vEmp.Fname, vEmp.Lname;
END; $$;

-- ✅ แก้ typo DEF  AULT → DEFAULT
CREATE OR REPLACE FUNCTION fnEmployeeLogin(
    pEmpNo      INT,
    pPassword   TEXT,
    pLineUserID VARCHAR(33) DEFAULT NULL
)
RETURNS TABLE (
    res_Success BOOLEAN,
    res_Message TEXT,
    res_EmpNo   INT
)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    vEmp Employee%ROWTYPE;
BEGIN
    SELECT * INTO vEmp FROM Employee e WHERE e.EmpNo = pEmpNo;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'ไม่พบรหัสพนักงาน', NULL::INT; RETURN;
    END IF;

    IF vEmp.WorkStatus IS DISTINCT FROM 'active' THEN
        RETURN QUERY SELECT FALSE, 'บัญชีถูกระงับ กรุณาติดต่อ ADMIN', NULL::INT; RETURN;
    END IF;

    IF vEmp.PasswordHash <> crypt(pPassword, vEmp.PasswordHash) THEN
        RETURN QUERY SELECT FALSE, 'รหัสผ่านไม่ถูกต้อง', NULL::INT; RETURN;
    END IF;

    UPDATE Employee SET
        LoginDate       = NOW(),
        LoginExpireDate = CURRENT_DATE + 7,
        LoginStatus     = 'active',
        LineUserID      = COALESCE(pLineUserID, LineUserID),
        IsBound         = CASE WHEN pLineUserID IS NOT NULL THEN TRUE ELSE IsBound END
    WHERE EmpNo = pEmpNo;

    RETURN QUERY SELECT TRUE, 'สำเร็จ', vEmp.EmpNo;
END; $$;

CREATE OR REPLACE FUNCTION fnAdminLogin(
    pUsername VARCHAR(20),
    pPassword TEXT
)
RETURNS TABLE (
    res_Success  BOOLEAN,
    res_Message  TEXT,
    res_Code     CHAR(6),
    res_Username VARCHAR(20),
    res_Token    CHAR(36),
    res_ScpName  VARCHAR(20),
    res_ScpCode  CHAR(6)
)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    vAdmin   Admin%ROWTYPE;
    vToken   CHAR(36);
    vScpName VARCHAR(20);
BEGIN
    SELECT * INTO vAdmin FROM Admin a WHERE a.Username = pUsername;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'ไม่พบ Username'::TEXT,
            NULL::CHAR(6), NULL::VARCHAR(20), NULL::CHAR(36),
            NULL::VARCHAR(20), NULL::CHAR(6); RETURN;
    END IF;

    IF vAdmin.PasswordHash <> crypt(pPassword, vAdmin.PasswordHash) THEN
        RETURN QUERY SELECT FALSE, 'รหัสผ่านไม่ถูกต้อง'::TEXT,
            NULL::CHAR(6), NULL::VARCHAR(20), NULL::CHAR(36),
            NULL::VARCHAR(20), NULL::CHAR(6); RETURN;
    END IF;

    SELECT ScpName INTO vScpName FROM SetCompany WHERE ScpCode = vAdmin.ScpCode;

    vToken := gen_random_uuid()::CHAR(36);

    UPDATE Admin SET
        Token       = vToken,
        LoginDate   = NOW(),
        ExpireDate  = CURRENT_DATE + 1,
        LoginStatus = 'active'
    WHERE Code = vAdmin.Code;

    RETURN QUERY SELECT TRUE, 'เข้าสู่ระบบสำเร็จ'::TEXT,
        vAdmin.Code, vAdmin.Username, vToken,
        vScpName, vAdmin.ScpCode;
END; $$;

CREATE OR REPLACE FUNCTION fnAdminChangePassword(
    pAdminCode       CHAR(6),
    pCurrentPassword TEXT,
    pNewPassword     TEXT
)
RETURNS TABLE (
    res_Success BOOLEAN,
    res_Message TEXT
)
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
    vAdmin Admin%ROWTYPE;
BEGIN
    SELECT * INTO vAdmin FROM Admin a WHERE a.Code = pAdminCode;

    IF NOT FOUND THEN
        RETURN QUERY SELECT FALSE, 'ไม่พบ Admin'::TEXT; RETURN;
    END IF;

    IF vAdmin.PasswordHash <> crypt(pCurrentPassword, vAdmin.PasswordHash) THEN
        RETURN QUERY SELECT FALSE, 'รหัสผ่านเดิมไม่ถูกต้อง'::TEXT; RETURN;
    END IF;

    IF LENGTH(pNewPassword) < 8 THEN
        RETURN QUERY SELECT FALSE, 'รหัสผ่านใหม่ต้องมีอย่างน้อย 8 ตัวอักษร'::TEXT; RETURN;
    END IF;

    IF pCurrentPassword = pNewPassword THEN
        RETURN QUERY SELECT FALSE, 'รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม'::TEXT; RETURN;
    END IF;

    UPDATE Admin SET
        PasswordHash = crypt(pNewPassword, gen_salt('bf')),
        Token        = NULL,
        LoginStatus  = NULL
    WHERE Code = pAdminCode;

    RETURN QUERY SELECT TRUE, 'เปลี่ยนรหัสผ่านสำเร็จ'::TEXT;
END; $$;