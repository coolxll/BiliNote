from app.db.models.video_tasks import VideoTask
from app.db.engine import get_db
from app.utils.logger import get_logger
from sqlalchemy.exc import IntegrityError

logger = get_logger(__name__)


# 插入任务（幂等）
def insert_video_task(video_id: str, platform: str, task_id: str) -> bool:
    db = next(get_db())
    try:
        existing = db.query(VideoTask).filter_by(task_id=task_id).first()
        if existing:
            if existing.video_id != video_id or existing.platform != platform:
                raise ValueError(
                    f"task_id 已绑定到其他视频: task_id={task_id}, "
                    f"existing=({existing.video_id}, {existing.platform}), "
                    f"requested=({video_id}, {platform})"
                )
            logger.info(
                f"Video task already exists, skip duplicate insert. "
                f"video_id: {video_id}, platform: {platform}, task_id: {task_id}"
            )
            return False

        task = VideoTask(video_id=video_id, platform=platform, task_id=task_id)
        db.add(task)
        db.commit()
        db.refresh(task)
        logger.info(f"Video task inserted successfully. video_id: {video_id}, platform: {platform}, task_id: {task_id}")
        return True
    except IntegrityError:
        # 并发重试可能在预检查后抢先插入；回滚后把同一任务视为幂等成功。
        db.rollback()
        existing = db.query(VideoTask).filter_by(task_id=task_id).first()
        if existing and existing.video_id == video_id and existing.platform == platform:
            logger.info(
                f"Video task already exists after concurrent insert, skip duplicate. "
                f"video_id: {video_id}, platform: {platform}, task_id: {task_id}"
            )
            return False
        logger.error(f"Failed to insert video task due to integrity error: task_id={task_id}", exc_info=True)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to insert video task: {e}", exc_info=True)
        raise
    finally:
        db.close()


# 查询任务（最新一条）
def get_task_by_video(video_id: str, platform: str):
    db = next(get_db())
    try:
        task = (
            db.query(VideoTask)
            .filter_by(video_id=video_id, platform=platform)
            .order_by(VideoTask.created_at.desc())
            .first()
        )
        if task:
            logger.info(f"Task found for video_id: {video_id} and platform: {platform}")
            return task.task_id
        else:
            logger.info(f"No task found for video_id: {video_id} and platform: {platform}")
            return None
    except Exception as e:
        logger.error(f"Failed to get task by video: {e}")
    finally:
        db.close()


# 删除任务
def delete_task_by_video(video_id: str, platform: str):
    db = next(get_db())
    try:
        tasks = (
            db.query(VideoTask)
            .filter_by(video_id=video_id, platform=platform)
            .all()
        )
        for task in tasks:
            db.delete(task)
        db.commit()
        logger.info(f"Task(s) deleted for video_id: {video_id} and platform: {platform}")
    except Exception as e:
        logger.error(f"Failed to delete task by video: {e}")
    finally:
        db.close()
