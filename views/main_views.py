from flask import Blueprint, request, current_app
from omegaconf import OmegaConf
from utils import Step1
from utils2 import Step2
from thumbnail import obj_to_fbx, obj_to_thumbnail, remove_bg
import os
import shutil
from config import db
from sqlalchemy import create_engine, text
import deepl

translator = deepl.Translator("a3e08092-e802-0017-285a-dc6070362a23:fx")

bp = Blueprint('main', __name__, url_prefix='/')

###################################### route
@bp.route('/obj')
def hello_pybo():
    return 'make_3d_obj'

@bp.route('/db', methods=['POST'])
def dbtest():
    try:
        data = request.get_json()

        # Create a connection from the engine
        connection = current_app.database.connect()

        query = text("""
            INSERT INTO generate_ai_path (
                objName,
                fileName,
                fbxName,
                textureName,
                objType,
                MakeTimeStamp
            ) VALUES (
                :objName,
                :fileName,
                :fbxName,
                :textureName,
                :objType,
                :MakeTimeStamp
            )
        """)

        new_data = connection.execute(query, {
            'objName': data.get('objName'),
            'fileName': data.get('fileName'),
            'fbxName': data.get('fbxName'),
            'textureName': data.get('textureName'),
            'objType': data.get('objType'),
            'MakeTimeStamp': data.get('MakeTimeStamp')
        })

        # Commit the transaction
        connection.commit()

        # Close the connection
        connection.close()

        return 'make_3d_obj'
    except Exception as e:
        return f"Error: {str(e)}"


@bp.route('/text2obj', methods=['GET', 'POST'])
def text_to_obj():
    prompt_txt = request.get_json()
    # print(prompt)
    prompt = prompt_txt['Prompt']
    timestamp = prompt_txt['MakeTimeStamp']
    print(prompt)
    
    config_path = "configs/text_mv.yaml"
    
    prompt = str(translator.translate_text(prompt, target_lang="en-us"))
    
    opt = OmegaConf.load(config_path)
    opt.prompt = 'full shot, a cute whole DSLR photo of ' + prompt
    opt.save_path = timestamp+'_'+prompt
    opt.outdir = 'static/text3d/'+timestamp+'_'+prompt
    # opt.outdir = 'static/text3d/'+prompt
    os.makedirs(opt.outdir, exist_ok=True)
    
    print('############################ path')
    print(opt.prompt)
    print(opt.save_path)
    print(opt.outdir)
    ################################## train_1
    step1 = Step1(opt)

    step1.train(opt.iters)   
    
    # ################################## train_2
    if opt.mesh is None:
        default_path = os.path.join(opt.outdir, opt.save_path + '_mesh.' + opt.mesh_format)
        if os.path.exists(default_path):
            opt.mesh = default_path
        else:
            raise ValueError(f"Cannot find mesh from {default_path}, must specify --mesh explicitly!")
    print(opt.mesh)
    
    # # step2까지 사용할지 결정하기
    # step2 = Step2(opt)
    
    # step2.train(opt.iters_refine)

    ################################## make_thumbnail
    # opt.outdir : folder_dir ex) data/prompt  
    # opt.mesh : obj_dir ex) data/prompt/prompt.obj
    # obj_dir = opt.mesh[:-9] + '.obj'
    # fbx_dir = obj_dir[:-3] + 'fbx'
    # texture_dir = obj_dir[:-4] + '_albedo.png'
    # thumbnail_dir = 'data/4-view_images/' + opt.save_path + '/_generated_one.png'
    thumbnail_dir = opt.outdir + '/' + opt.save_path + '_generated_one.png'

    obj_to_fbx(opt.mesh, opt.mesh[:-3]+'fbx')
    # obj_to_thumbnail(obj_dir, texture_dir)
    remove_bg(thumbnail_dir)
    
    ################################## docker 파일 잠금 문제 해결하기
    # parser : chmod 777 -R ./data
    # terminal_command = "sudo "
    
    # shutil.move(thumbnail_dir, 'static/text3d/thumb')
    shutil.move(opt.outdir + '/' + opt.save_path + '_mesh.fbx', 'static/text3d/fbx')
    shutil.move(opt.outdir + '/' + opt.save_path + '_rm.png', 'static/text3d/thumb')
    shutil.move(opt.outdir + '/' + opt.save_path + '_mesh_albedo.png', 'static/text3d/texture')

    # MySQL 데이터베이스에 정보 저장
    # make_time = prompt_txt['MakeTimeStamp']
    connection = current_app.database.connect()

    query = text("""
        INSERT INTO generate_ai_path (
            objName,
            fileName,
            fbxName,
            textureName,
            objType,
            MakeTimeStamp
        ) VALUES (
            :objName,
            :fileName,
            :fbxName,
            :textureName,
            :objType,
            :MakeTimeStamp
        )
    """)

    new_data = connection.execute(query, {
        'objName': opt.save_path+'_rm', #'/home/meta-ai2/bibimpang_serve/'+opt.outdir+'_mesh.obj',
        'fileName': opt.save_path+'_rm', # thumbnail
        'fbxName': opt.save_path+'_mesh.fbx',
        'textureName': opt.save_path+'_mesh_albedo.png',
        'objType': 'TS3',
        'MakeTimeStamp': timestamp
    })

    # Commit the transaction
    connection.commit()

    # Close the connection
    connection.close()

    return 'finish_create_obj'