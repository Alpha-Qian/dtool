#READ ME
一个用python编写的协程并发下载工具
##使用说明：
dtool.py：主要功能文件
DownloadFile(url,path= './')初始化文件下载类，参数url必须为完整url，参数path不起作用，只是一个占位符，文件默认保存在当前文件夹

使用main(pre_task_num,auto= True)方法来启动下载，pre_task_num指定下载连接数，auto为True则会在pre_task_num的基础上根据网络状况自动添加连接数
