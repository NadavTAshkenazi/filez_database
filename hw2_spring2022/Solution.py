from typing import List
import Utility.DBConnector as Connector
from Utility.Status import Status
from Utility.Exceptions import DatabaseException
from Business.File import File
from Business.RAM import RAM
from Business.Disk import Disk
from psycopg2 import sql


def createTables():
    conn = None
    try:
        conn = Connector.DBConnector()
        conn.execute("""CREATE TABLE Files(
                    id INTEGER PRIMARY KEY CHECK(id > 0),
                    type TEXT NOT NULL, 
                    size_needed INTEGER NOT NULL, 
                    CHECK (id > 0),
                    CHECK (size_needed >= 0));
                    """)
        conn.execute("""CREATE TABLE Disks(
                    id INTEGER PRIMARY KEY CHECK(id > 0),
                    company TEXT NOT NULL, 
                    speed INTEGER NOT NULL,
                    free_space INTEGER NOT NULL,
                    cost INTEGER NOT NULL,
                    CHECK (id > 0),
                    CHECK (speed > 0),
                    CHECK (free_space >= 0),
                    CHECK (cost > 0));
                    """)
        conn.execute("""CREATE TABLE RAMs(
                    id INTEGER PRIMARY KEY CHECK(id > 0),
                    company TEXT NOT NULL, 
                    size INTEGER NOT NULL,
                    CHECK (id > 0),
                    CHECK (size > 0));
                    """)

        # === additional tables ====

        conn.execute("""CREATE TABLE FilesOfDisk(
                    File_id INTEGER NOT NULL REFERENCES Files(id) ON DELETE CASCADE,
                    Disk_id INTEGER NOT NULL REFERENCES Disks(id) ON DELETE CASCADE,
                    PRIMARY KEY(File_id, Disk_id));
                    """)

        conn.execute("""CREATE TABLE RAMsOfDisk(
                    RAM_id INTEGER NOT NULL REFERENCES RAMS(id) ON DELETE CASCADE,
                    Disk_id INTEGER NOT NULL REFERENCES Disks(id) ON DELETE CASCADE,
                    PRIMARY KEY(RAM_id, Disk_id));
                    """)

        conn.execute("""CREATE TABLE DisksCheck(
                    id INTEGER NOT NULL REFERENCES Disks(id) ON DELETE CASCADE,
                    PRIMARY KEY(id));
                    """)

        # === views ====

        conn.execute("""CREATE VIEW RAMSizeOFDisk AS
                        SELECT RAMsOfDisk.Disk_id, SUM(RAMs.size) as totalRAMSize
                        FROM  RAMs, RAMsOfDisk
                        WHERE RAMs.id = RAMsOfDisk.RAM_id
                        GROUP BY RAMsOfDisk.Disk_id;
                        """)

        conn.execute("""CREATE VIEW PotentialFilesForDisk AS
                        SELECT DISTINCT Disks.id as Disk_id, Files.id AS File_id
                        FROM Disks, Files
                        WHERE Files.size_needed <= Disks.free_space;
                        """)
        conn.execute("""CREATE VIEW FilesWithCommonDisks AS
                        SELECT DISTINCT FOD1.file_id AS file_id1, FOD2.file_id AS file_id2, FOD1.disk_id AS disk_id 
                        FROM FilesOFDisk AS FOD1, FilesOFDisk AS FOD2
                        WHERE (FOD1.disk_id = FOD2.disk_id
                               AND FOD1.file_id != FOD2.file_id)
                        ORDER BY file_id1 ASC;  
                        """)
        conn.execute("""CREATE VIEW CommonDisksCount AS
                        SELECT FilesWithCommonDisks.file_id1 as file_id, FilesWithCommonDisks.file_id2 as shared_file_id, COUNT(FilesWithCommonDisks.disk_id) as sharedDisksCount
                        FROM FilesWithCommonDisks
                        GROUP BY FilesWithCommonDisks.file_id1, FilesWithCommonDisks.file_id2
                        ORDER BY file_id ASC  
                        """)

        conn.execute("""CREATE VIEW CommonVSTotalDisks AS
                        SELECT CommonDisksCount.file_id, CommonDisksCount.shared_file_id, CommonDisksCount.shareddiskscount,  count(filesOfDisk.disk_id) as totalDisks
                        FROM CommonDisksCount, filesOfDisk
                        WHERE CommonDisksCount.file_id = filesOfDisk.file_id
                        GROUP BY CommonDisksCount.file_id, CommonDisksCount.shared_file_id, CommonDisksCount.shareddiskscount  
                        """)

        # close files union with empty way close files (files not on disks are close to every file)
        conn.execute("""CREATE VIEW isCloseFiles AS
						SELECT file_id, shared_file_id, (shareddiskscount *2 >= totalDisks) as isClose
                        FROM CommonVSTotalDisks

						UNION 

						(SELECT F1.id as file_id, F2.id as shared_file_id, true as isClose
						FROM FILES F1, FILES F2
						WHERE (F1.id not in (SELECT file_id from FilesOfDisk) AND F1.id != F2.id))

                        """)

        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()
    finally:
        conn.close()


def clearTables():
    conn = None
    try:
        conn = Connector.DBConnector()
        conn.execute("DELETE FROM Files")
        conn.execute("DELETE FROM Disks")
        conn.execute("DELETE FROM RAMs")
        conn.execute("DELETE FROM FilesOfDisk")
        conn.execute("DELETE FROM RAMsOfDisk")
        conn.execute("DELETE FROM DisksCheck")

        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()
    finally:
        conn.close()


def dropTables():
    conn = None
    try:
        conn = Connector.DBConnector()
        conn.execute("DROP VIEW IF EXISTS RAMSizeOFDisk CASCADE")
        conn.execute("DROP VIEW IF EXISTS PotentialFilesForDisk CASCADE")
        conn.execute("DROP VIEW IF EXISTS FilesWithCommonDisks CASCADE")
        conn.execute("DROP VIEW IF EXISTS CommonDisksCount CASCADE")
        conn.execute("DROP VIEW IF EXISTS CommonVSTotalDisks CASCADE")
        conn.execute("DROP VIEW IF EXISTS isCloseFiles CASCADE")

        conn.execute("DROP TABLE IF EXISTS Files CASCADE")
        conn.execute("DROP TABLE IF EXISTS Disks CASCADE")
        conn.execute("DROP TABLE IF EXISTS RAMs CASCADE")
        conn.execute("DROP TABLE IF EXISTS FilesOfDisk CASCADE")
        conn.execute("DROP TABLE IF EXISTS RAMsOfDisk CASCADE")
        conn.execute("DROP TABLE IF EXISTS DisksCheck CASCADE")

        conn.commit()
    except Exception as e:
        print(e)
        conn.rollback()
    finally:
        conn.close()


# ========= AUX FUNCS ===========

def createDisk(query_result: tuple) -> Disk:
    return Disk(diskID=query_result[0], company=query_result[1], speed=query_result[2], free_space=query_result[3],
                cost=query_result[4])


def createFile(query_result: tuple) -> Disk:
    return File(fileID=query_result[0], type=query_result[1], size=query_result[2])


def createRAM(query_result: tuple) -> Disk:
    return RAM(ramID=query_result[0], company=query_result[1], size=query_result[2])


# ========= CRUD API ===========
def addFile(file: File) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL(""" INSERT INTO Files(id, type, size_needed) 
                            VALUES({id}, {type} ,{size});
                            """).format(id=sql.Literal(file.getFileID()), type=sql.Literal(file.getType()),
                                        size=sql.Literal(file.getSize()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
    except DatabaseException.NOT_NULL_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.CHECK_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.UNIQUE_VIOLATION:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except Exception:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def getFileByID(fileID: int) -> File:
    conn = None
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""SELECT *
                           FROM Files
                           WHERE id = {id};
                           """).format(id=sql.Literal(fileID))
        rows_effected, result = conn.execute(query)
        if rows_effected == 0:
            file = File.badFile()
        else:
            file = createFile(result.rows[0])
        conn.commit()
    except Exception:
        file = File.badFile()
        conn.rollback()

    finally:
        conn.close()
    return file


def deleteFile(file: File) -> Status:  # todo: adjust free space
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            UPDATE Disks
                            set free_space = Disks.free_space + 
                            COALESCE ((SELECT Files.size_needed 
                                        FROM FilesOfDisk, Files
                                         WHERE Disks.id = FilesOfDisk.Disk_id
                                                AND FilesOfDisk.File_id = Files.id 
                                                AND Files.id = {fileID}), 0);
                            DELETE FROM Files WHERE id=({fileID});

                            """).format(fileID=sql.Literal(file.getFileID()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def addDisk(disk: Disk) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL(""" INSERT INTO Disks(id, company, speed, free_space, cost) 
                            VALUES ({id}, {company}, {speed}, {free_space}, {cost});
                            """).format(id=sql.Literal(disk.getDiskID()), company=sql.Literal(disk.getCompany()),
                                        speed=sql.Literal(disk.getSpeed()), free_space=sql.Literal(disk.getFreeSpace()),
                                        cost=sql.Literal(disk.getCost()))

        rows_effected, _ = conn.execute(query)
        conn.commit()
    except DatabaseException.NOT_NULL_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.CHECK_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.UNIQUE_VIOLATION:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except Exception as e:
        print(e)
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def getDiskByID(diskID: int) -> Disk:
    conn = None
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                           SELECT *
                           FROM Disks
                           WHERE id = {id};

                           """).format(id=sql.Literal(diskID))
        rows_effected, result = conn.execute(query)
        if rows_effected == 0:
            disk = Disk.badDisk()
        else:
            disk = createDisk(result.rows[0])
    except Exception as e:
        disk = Disk.badDisk()
        conn.rollback()

    finally:
        conn.close()
    return disk


def deleteDisk(diskID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""DELETE FROM Disks
                            WHERE Disks.id={id};
                            """).format(id=sql.Literal(diskID))
        rows_effected, _ = conn.execute(query)
        if rows_effected == 0:
            ret = Status.NOT_EXISTS
        conn.commit()
    except Exception as e:
        ret = Status.ERROR
        conn.rollback()
    finally:
        conn.close()
    return ret


def addRAM(ram: RAM) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            INSERT INTO RAMS(id, size, company) 
                            VALUES({id}, {RAMSize}, {company});
                            """).format(id=sql.Literal(ram.getRamID()), RAMSize=sql.Literal(ram.getSize()),
                                        company=sql.Literal(ram.getCompany()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
    except DatabaseException.NOT_NULL_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.CHECK_VIOLATION:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.UNIQUE_VIOLATION:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def getRAMByID(ramID: int) -> RAM:
    conn = None
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""SELECT *
                           FROM RAMs
                           WHERE id = {id}
                           """).format(id=sql.Literal(ramID))
        rows_effected, result = conn.execute(query)
        if rows_effected == 0:
            ram = RAM.badRAM()
        else:
            ram = createRAM(result.rows[0])
        conn.commit()
    except Exception:
        ram = RAM.badRAM()
        conn.rollback()

    finally:
        conn.close()
    return ram


def deleteRAM(ramID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""DELETE FROM RAMs
                            WHERE id={id};
                             """).format(id=sql.Literal(ramID))
        rows_effected, _ = conn.execute(query)
        if rows_effected == 0:
            ret = Status.NOT_EXISTS
        conn.commit()

    except Exception:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def addDiskAndFile(disk: Disk, file: File) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            INSERT INTO Files(id, type, size_needed)
                            VALUES({fileID}, {fileType} ,{fileSize});
                            INSERT INTO Disks(id, company, speed, free_space,cost)
                            VALUES({diskID}, {diskCompany}, {diskSpeed}, {diskFreeSpace}, {diskCost});
                            """).format(fileID=sql.Literal(file.getFileID()),
                                        fileType=sql.Literal(file.getType()),
                                        fileSize=sql.Literal(file.getSize()),
                                        diskID=sql.Literal(disk.getDiskID()),
                                        diskCompany=sql.Literal(disk.getCompany()),
                                        diskSpeed=sql.Literal(disk.getSpeed()),
                                        diskFreeSpace=sql.Literal(disk.getFreeSpace()),
                                        diskCost=sql.Literal(disk.getCost()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
    except DatabaseException.UNIQUE_VIOLATION:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def addFileToDisk(file: File, diskID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            UPDATE Disks
                            set free_space = Disks.free_space - 
                                COALESCE((SELECT Files.size_needed
                                FROM Files
                                WHERE Files.id = {file_ID}), 0)
                            WHERE Disks.id = {disk_ID};

                            INSERT INTO FilesOfDisk(File_id, Disk_id)
                            VALUES ({file_ID}, {disk_ID});
                            """).format(disk_ID=sql.Literal(diskID), file_ID=sql.Literal(file.getFileID()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
        if rows_effected == 0:
            ret = Status.NOT_EXISTS

    except DatabaseException.NOT_NULL_VIOLATION as e:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.CHECK_VIOLATION as e:
        ret = Status.BAD_PARAMS
        conn.rollback()

    except DatabaseException.UNIQUE_VIOLATION as e:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except DatabaseException.FOREIGN_KEY_VIOLATION:
        ret = Status.NOT_EXISTS
        conn.rollback()

    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def removeFileFromDisk(file: File, diskID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            UPDATE Disks
                            set free_space = Disks.free_space + 
                            COALESCE ((SELECT Files.size_needed 
                                        FROM FilesOfDisk, Files
                                         WHERE {disk_id} = FilesOfDisk.Disk_id
                                                AND FilesOfDisk.File_id = Files.id 
                                                AND Files.id = {file_id}), 0)
                            WHERE Disks.id = {disk_id};
                            DELETE 
                            FROM FilesOfDisk 
                            WHERE FilesOfDisk.File_id={file_id};
                            """).format(disk_id=sql.Literal(diskID), file_id=sql.Literal(file.getFileID()))
        rows_effected, _ = conn.execute(query)
        conn.commit()
    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def addRAMToDisk(ramID: int, diskID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            INSERT INTO RAMsOfDisk(RAM_id, Disk_id)
                            VALUES ({ram_id}, {disk_id});
                            """).format(ram_id=sql.Literal(ramID), disk_id=sql.Literal(diskID))
        rows_effected, _ = conn.execute(query)
        if rows_effected == 0:
            ret = Status.NOT_EXISTS
        conn.commit()
    except DatabaseException.UNIQUE_VIOLATION:
        ret = Status.ALREADY_EXISTS
        conn.rollback()

    except DatabaseException.FOREIGN_KEY_VIOLATION:
        ret = Status.NOT_EXISTS
        conn.rollback()

    except Exception as e:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def removeRAMFromDisk(ramID: int, diskID: int) -> Status:
    conn = None
    ret = Status.OK
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                            DELETE FROM RAMsOfDisk
                            WHERE RAM_id={ram_id} and Disk_id={disk_id};
                            """).format(ram_id=sql.Literal(ramID), disk_id=sql.Literal(diskID))
        rows_effected, _ = conn.execute(query)
        if rows_effected == 0:
            ret = Status.NOT_EXISTS
        conn.commit()
    except Exception:
        ret = Status.ERROR
        conn.rollback()

    finally:
        conn.close()
    return ret


def averageFileSizeOnDisk(diskID: int) -> float:
    conn = None
    average = 0
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                        BEGIN;
                        SELECT AVG(Files.size_needed)
                        FROM Files, FilesOfDisk
                        WHERE Files.id = FilesOfDisk.File_id
                            AND FilesOfDisk.Disk_id = {disk_id};

                        """).format(disk_id=sql.Literal(diskID))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            average = 0
        else:
            average = result.rows[0][0]
        conn.commit()
    except Exception as e:
        average = -1
    finally:
        conn.close()
        return average


def diskTotalRAM(diskID: int) -> int:
    conn = None
    total = 0
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                        BEGIN;
                        SELECT totalRAMSize
                        FROM RAMSizeOFDisk
                        WHERE RAMSizeOFDisk.Disk_id = {disk_id};
                        """).format(disk_id=sql.Literal(diskID))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            total = 0
        else:
            total = result.rows[0][0]
        conn.commit()
    except Exception as e:
        total = -1
        conn.rollback()
    finally:
        conn.close()
        return total


def getCostForType(type: str) -> int:
    conn = None
    cost = 0
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                         BEGIN;
                         SELECT SUM(Disks.cost * Files.size_needed)
                         FROM Disks, Files, FilesOfDisk
                         WHERE Disks.id = FilesOfDisk.Disk_id
                             AND FilesOfDisk.File_id = Files.id
                             AND Files.type = {type};
                         """).format(type=sql.Literal(type))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            cost = 0
        else:
            cost = result.rows[0][0]
        conn.commit()
    except Exception as e:
        cost = -1
    finally:
        conn.close()
        return cost


def getFilesCanBeAddedToDisk(diskID: int) -> List[int]:
    conn = None
    fileIDsList = []
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                             BEGIN;
                             SELECT DISTINCT potentialFilesForDisk.file_id AS id
                             FROM potentialFilesForDisk
                             WHERE (potentialFilesForDisk.disk_id = {disk_id})
                             ORDER BY id DESC
                             LIMIT 5;  
                             """).format(disk_id=sql.Literal(diskID))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            fileIDsList = []
        else:
            fileIDsList = [x[0] for x in result.rows]
        conn.commit()
    except Exception as e:
        fileIDsList = []
    finally:
        conn.close()
        return fileIDsList


def getFilesCanBeAddedToDiskAndRAM(diskID: int) -> List[int]:
    conn = None
    fileIDsList = []
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                             SELECT DISTINCT Files.id AS id
                             FROM Disks, Files, RAMSizeOFDisk
                             WHERE (Files.size_needed <= Disks.free_space
                                    AND Disks.id = {disk_id})
                                AND (Files.size_needed <= RAMSizeOFDisk.totalRAMSize
                                    AND RAMSizeOFDisk.Disk_id = {disk_id})
                             ORDER BY id ASC
                             LIMIT 5;      
                             """).format(disk_id=sql.Literal(diskID))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            fileIDsList = []
        else:
            fileIDsList = [x[0] for x in result.rows]
        conn.commit()
    except Exception as e:
        fileIDsList = []
    finally:
        conn.close()
        return fileIDsList


def isCompanyExclusive(diskID: int) -> bool:
    conn = None
    isExclusive = False
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""
                             BEGIN;
                             INSERT INTO DisksCheck(id)
                             VALUES({disk_id});
                             DELETE FROM DisksCheck WHERE id=({disk_id});
                             SELECT DISTINCT RAMs.company
                             FROM Disks, RAMSOFDisk, RAMs
                             WHERE (Disks.id = RAMSOFDisk.Disk_id
                                    AND Disks.id = {disk_id}                            
                                    AND RAMSOFDisk.RAM_id = RAMs.id
                                    AND RAMs.company != Disks.company);
                             """).format(disk_id=sql.Literal(diskID))
        rows_effected, result = conn.execute(query)
        if rows_effected == 0:
            isExclusive = True
        else:
            isExclusive = False
        conn.commit()
    except Exception as e:
        isExclusive = False
        conn.rollback()

    finally:
        conn.close()
        return isExclusive


def getConflictingDisks() -> List[int]:
    conn = None
    conflictingDisks = []
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                             SELECT DISTINCT FOD1.disk_id AS id
                             FROM FilesOFDisk AS FOD1, FilesOFDisk AS FOD2
                             WHERE (FOD1.disk_id != FOD2.disk_id
                                    AND FOD1.file_id = FOD2.file_id)
                             ORDER BY id ASC;  
                             """)
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            conflictingDisks = []
        else:
            conflictingDisks = [x[0] for x in result.rows]
        conn.commit()
    except Exception as e:
        conflictingDisks = []
    finally:
        conn.close()
        return conflictingDisks


def mostAvailableDisks() -> List[int]:
    conn = None
    availableDisks = []
    try:
        conn = Connector.DBConnector()
        query = sql.SQL("""BEGIN;
                             SELECT potentialFilesForDisk.disk_id AS disk_id, COUNT(potentialFilesForDisk.file_id) as filesCount, Disks.speed
                             FROM potentialFilesForDisk, Disks
                             WHERE (potentialFilesForDisk.disk_id = Disks.id)
                             GROUP BY potentialFilesForDisk.disk_id, Disks.speed
                             ORDER BY filesCount DESC, speed DESC, disk_id ASC
                             LIMIT 5;
                             """)
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            availableDisks = []
        else:
            availableDisks = [x[0] for x in result.rows]
        conn.commit()
    except Exception as e:
        availableDisks = []
    finally:
        conn.close()
        return availableDisks


def getCloseFiles(fileID: int) -> List[int]:
    conn = None
    closeFiles = []
    try:
        conn = Connector.DBConnector()
        query = sql.SQL(""" BEGIN;
                            SELECT shared_file_id
                            FROM isclosefiles
                            WHERE isClose = true
                                    AND file_id = {file_id}
                            ORDER BY shared_file_id ASC
                            LIMIT 10;
                             """).format(file_id=sql.Literal(fileID))
        _, result = conn.execute(query)
        if result.rows[0][0] == None:
            closeFiles = []
        else:
            closeFiles = [x[0] for x in result.rows]
        conn.commit()
    except Exception as e:
        closeFiles = []
    finally:
        conn.close()
        return closeFiles

    return []
