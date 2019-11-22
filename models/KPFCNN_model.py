#
#
#      0=================================0
#      |    Kernel Point Convolutions    |
#      0=================================0
#
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Segmentation model
#
# ----------------------------------------------------------------------------------------------------------------------
#
#      Hugues THOMAS - 11/06/2018
#


# ----------------------------------------------------------------------------------------------------------------------
#
#           Imports and global variables
#       \**********************************/
#


# Basic libs
from os import makedirs
from os.path import exists
import time
import tensorflow as tf
import sys
import numpy as np
import shutil 
import os

# Convolution functions
# from models.network_blocks import assemble_FCNN_blocks
from models.D2Net import assemble_FCNN_blocks
from loss import cdist, LOSS_CHOICES


# ----------------------------------------------------------------------------------------------------------------------
#
#           Model Class
#       \*****************/
#


class KernelPointFCNN:

    def __init__(self, flat_inputs, config):
        """
        Initiate the model
        :param flat_inputs: List of input tensors (flatten)
        :param config: configuration class
        """

        # Model parameters
        self.config = config
        self.tensorboard_root = ''
        # Path of the result folder
        if self.config.saving:
            if self.config.saving_path == None:
                # self.saving_path = time.strftime('results/Log_%Y-%m-%d_%H-%M-%S', time.gmtime())
                self.saving_path = time.strftime('results/Log_%m%d%H%M')
                if self.config.is_test:
                    experiment_id = "KPConv" + time.strftime('%m%d%H%M') + "test"
                else:
                    experiment_id = "KPConv" + time.strftime('%m%d%H%M')
                snapshot_root = 'snapshot/%s' % experiment_id
                os.makedirs(snapshot_root, exist_ok=True)
                tensorboard_root = 'tensorboard/%s' % experiment_id
                os.makedirs(tensorboard_root, exist_ok=True)
                shutil.copy2(os.path.join('.', 'models/network_blocks.py'), os.path.join(snapshot_root, 'network_blocks.py'))
                shutil.copy2(os.path.join('.', 'kernels/convolution_ops.py'), os.path.join(snapshot_root, 'conv_ops.py'))
                shutil.copy2(os.path.join('.', 'training_3DMatch.py'), os.path.join(snapshot_root, 'train.py'))
                shutil.copy2(os.path.join('.', 'utils/trainer.py'), os.path.join(snapshot_root, 'trainer.py'))
                shutil.copy2(os.path.join('.', 'models/D2Net.py'), os.path.join(snapshot_root, 'model.py'))
                shutil.copy2(os.path.join('.', 'models/KPFCNN_model.py'), os.path.join(snapshot_root, 'model_true.py'))
                shutil.copy2(os.path.join('.', 'datasets/ThreeDMatch.py'), os.path.join(snapshot_root, 'dataset.py'))
                shutil.copy2(os.path.join('.', 'loss.py'), os.path.join(snapshot_root, 'loss.py'))
                self.tensorboard_root = tensorboard_root
            else:
                self.saving_path = self.config.saving_path
            if not exists(self.saving_path):
                makedirs(self.saving_path)

        ########
        # Inputs
        ########
        # Sort flatten inputs in a dictionary
        with tf.variable_scope('anchor_inputs'):
            self.anchor_inputs = dict()
            self.anchor_inputs['points'] = flat_inputs[:config.num_layers]
            self.anchor_inputs['neighbors'] = flat_inputs[config.num_layers:2 * config.num_layers]
            self.anchor_inputs['pools'] = flat_inputs[2 * config.num_layers:3 * config.num_layers]
            self.anchor_inputs['upsamples'] = flat_inputs[3 * config.num_layers:4 * config.num_layers]
            ind = 4 * config.num_layers
            self.anchor_inputs['features'] = flat_inputs[ind]
            ind += 1
            self.anchor_inputs['batch_weights'] = flat_inputs[ind]
            ind += 1
            self.anchor_inputs['in_batches'] = flat_inputs[ind]
            ind += 1
            self.anchor_inputs['out_batches'] = flat_inputs[ind]
            ind += 1
            # self.anchor_inputs['augment_scales'] = flat_inputs[ind]
            # ind += 1
            # self.anchor_inputs['augment_rotations'] = flat_inputs[ind]
            # ind += 1
            # self.anchor_inputs['object_inds'] = flat_inputs[ind]
            # ind += 1
            self.anchor_inputs['stack_lengths'] = flat_inputs[ind]
            ind += 1
            self.anchor_keypts_inds = tf.squeeze(flat_inputs[ind])
            ind += 1
            self.positive_keypts_inds = tf.squeeze(flat_inputs[ind])
            ind += 1 
            self.anc_id = flat_inputs[ind][0]
            self.pos_id = flat_inputs[ind][1]
            ind += 1
            self.anchor_inputs['backup_points'] = flat_inputs[ind]
            if config.dataset == 'KITTI':
                ind += 1
                self.anchor_inputs['trans'] = flat_inputs[ind]
            # self.object_inds = self.anchor_inputs['object_inds']            
            self.dropout_prob = tf.placeholder(tf.float32, name='dropout_prob')

        ########
        # Layers
        ########

        # Create layers
        # with tf.device('/gpu:%d' % config.gpu_id):
        with tf.variable_scope('KernelPointNetwork', reuse=False) as scope:
            # self.out_features, self.out_scores, self.anc_key, self.pos_key, self.keypts_distance = assemble_FCNN_blocks(self.anchor_inputs, self.config, self.dropout_prob)
            # condition = self.dropout_prob < 0.99
            # def true_fn(): # for training
            #     return tf.cast(self.anc_key, tf.int32), tf.cast(self.pos_key, tf.int32), self.keypts_distance
            # def false_fn(): # for evalidation 
            #     anc_keypts = tf.gather(self.anchor_inputs['backup_points'], self.anchor_keypts_inds)
            #     keypts_distance = cdist(anc_keypts, anc_keypts, metric='euclidean')
            #     return self.anchor_keypts_inds, self.positive_keypts_inds, keypts_distance
            # self.anchor_keypts_inds, self.positive_keypts_inds, self.keypts_distance = tf.cond(condition, true_fn, false_fn)
            self.out_features, self.out_scores  = assemble_FCNN_blocks(self.anchor_inputs, self.config, self.dropout_prob)
            anc_keypts = tf.gather(self.anchor_inputs['backup_points'], self.anchor_keypts_inds)
            self.keypts_distance = cdist(anc_keypts, anc_keypts, metric='euclidean')
            # self.anchor_keypts_inds, self.positive_keypts_inds, self.keypts_distance = self.anc_key, self.pos_key, self.keypts_distance
        
        # show all the trainable vairble
        all_trainable_vars = tf.trainable_variables()
        for i in range(len(all_trainable_vars)):
            print(i, all_trainable_vars[i])
        ########
        # Losses
        ########

        with tf.variable_scope('loss'):
            # anchor_list = tf.split(self.output_features_anchor, num_or_size_splits=1, axis=0)
            # positive_list = tf.split(self.output_features_positive, num_or_size_splits=1, axis=0)
            # loss_list = []
            # acc_list = []
            # for i in range(1):
            #     positiveIDS = tf.range(tf.shape(anchor_list[i])[0])
            #     positiveIDS = tf.reshape(positiveIDS, [tf.shape(anchor_list[i])[0]])
            #     dists = cdist(anchor_list[i], positive_list[i], metric='euclidean')
            #     batchhard_loss, accuracy = LOSS_CHOICES['batch_hard'](dists, positiveIDS, margin=1)
            #     loss_list.append(batchhard_loss)
            #     acc_list.append(accuracy)
            # self.batchhard_loss = tf.reduce_mean(tf.stack(loss_list))
            # self.accuracy = tf.reduce_mean(tf.stack(acc_list))
            positiveIDS = tf.range(tf.size(self.anchor_keypts_inds))
            positiveIDS = tf.reshape(positiveIDS, [tf.size(self.anchor_keypts_inds)])
            self.anchor_keypoints_feat = tf.gather(self.out_features, self.anchor_keypts_inds)
            self.positive_keypoints_feat = tf.gather(self.out_features, self.positive_keypts_inds)
            dists = cdist(self.anchor_keypoints_feat, self.positive_keypoints_feat, metric='euclidean')
            self.dists = dists
            # to avoid false negative. safe radius is important.
            same_identity_mask = tf.equal(tf.expand_dims(positiveIDS, axis=1), tf.expand_dims(positiveIDS, axis=0))
            false_negative_mask = tf.less(self.keypts_distance, config.safe_radius)
            mask = tf.logical_and(false_negative_mask, tf.logical_not(same_identity_mask))
            self.dists += tf.scalar_mul(10, tf.cast(mask, tf.float32))
            # dists = cdist(self.output_features_anchor[self.keypts_inds], self.output_features_positive[self.keypts_inds], metric='euclidean')
            self.batchhard_loss, self.accuracy, self.average_dist = LOSS_CHOICES['batch_hard'](self.dists, positiveIDS, margin=1)
            if config.repeat_loss_weight != 0:
                self.anchor_scores = tf.gather(self.out_scores, self.anchor_keypts_inds)
                self.positve_scores = tf.gather(self.out_scores, self.positive_keypts_inds)
                self.repeat_loss = LOSS_CHOICES['repeat_loss'](self.dists, self.anchor_scores, self.positve_scores, positiveIDS, margin=1)
                self.repeat_loss = tf.scalar_mul(self.config.repeat_loss_weight, self.repeat_loss)
            else:
                self.repeat_loss = tf.constant(0, dtype=self.batchhard_loss.dtype)

            # if the number of correspondence is less than half of keypts num, then skip
            enough_keypts_num = tf.constant(0.5 * config.keypts_num)
            condition = tf.less_equal(enough_keypts_num, tf.cast(tf.size(self.anchor_keypts_inds), tf.float32))
            def true_fn(): 
                return self.batchhard_loss, self.repeat_loss, self.accuracy, self.average_dist
            def false_fn(): 
                return tf.constant(0, dtype=self.batchhard_loss.dtype), tf.constant(0, dtype=self.repeat_loss.dtype), tf.constant(-1, dtype=self.accuracy.dtype), tf.constant(0, dtype=self.average_dist.dtype)
            self.batchhard_loss, self.repeat_loss, self.accuracy, self.average_dist = tf.cond(condition, true_fn, false_fn)
            # self.l2_loss = tf.math.scalar_mul(0.0, tf.reduce_mean(tf.norm(self.output_features_anchor - self.output_features_positive, ord='euclidean')))
            # Add regularization
            # self.loss = self.regularization_losses() + self.batchhard_loss + self.l2_loss
            # Get L2 norm of all weights
            regularization_losses = [tf.nn.l2_loss(v) for v in tf.global_variables() if 'weights' in v.name]
            self.regularization_loss = self.config.weights_decay * tf.add_n(regularization_losses)
            self.loss = self.batchhard_loss + self.repeat_loss + self.regularization_loss
        tf.summary.scalar('batch hard loss', self.batchhard_loss)
        tf.summary.scalar('accuracy', self.accuracy)
        tf.summary.scalar('repeat loss', self.repeat_loss)
        tf.summary.scalar('average dist', self.average_dist)
        self.merged = tf.summary.merge_all()
        if self.tensorboard_root != '':
            self.train_writer = tf.summary.FileWriter(self.tensorboard_root + '/train/')
            self.val_writer = tf.summary.FileWriter(self.tensorboard_root + '/val/')


        return

    def regularization_losses(self):

        #####################
        # Regularizatizon loss
        #####################

        # Get L2 norm of all weights
        regularization_losses = [tf.nn.l2_loss(v) for v in tf.global_variables() if 'weights' in v.name]
        self.regularization_loss = self.config.weights_decay * tf.add_n(regularization_losses)

        ##############################
        # Gaussian regularization loss
        ##############################

        gaussian_losses = []
        for v in tf.global_variables():
            if 'kernel_extents' in v.name:
                # Layer index
                layer = int(v.name.split('/')[1].split('_')[-1])

                # Radius of convolution for this layer
                conv_radius = self.config.first_subsampling_dl * self.config.density_parameter * (2 ** (layer - 1))

                # Target extent
                target_extent = conv_radius / 1.5
                gaussian_losses += [tf.nn.l2_loss(v - target_extent)]

        if len(gaussian_losses) > 0:
            self.gaussian_loss = self.config.gaussian_decay * tf.add_n(gaussian_losses)
        else:
            self.gaussian_loss = tf.constant(0, dtype=tf.float32)

        #############################
        # Offsets regularization loss
        #############################

        offset_losses = []

        if self.config.offsets_loss == 'permissive':

            for op in tf.get_default_graph().get_operations():
                if op.name.endswith('deformed_KP'):
                    # Get deformed positions
                    deformed_positions = op.outputs[0]

                    # Layer index
                    layer = int(op.name.split('/')[1].split('_')[-1])

                    # Radius of deformed convolution for this layer
                    conv_radius = self.config.first_subsampling_dl * self.config.density_parameter * (2 ** layer)

                    # Normalized KP locations
                    KP_locs = deformed_positions / conv_radius

                    # Loss will be zeros inside radius and linear outside radius
                    # Mean => loss independent from the number of input points
                    radius_outside = tf.maximum(0.0, tf.norm(KP_locs, axis=2) - 1.0)
                    offset_losses += [tf.reduce_mean(radius_outside)]


        elif self.config.offsets_loss == 'fitting':

            for op in tf.get_default_graph().get_operations():

                if op.name.endswith('deformed_d2'):
                    # Get deformed distances
                    deformed_d2 = op.outputs[0]

                    # Layer index
                    layer = int(op.name.split('/')[1].split('_')[-1])

                    # Radius of deformed convolution for this layer
                    KP_extent = self.config.first_subsampling_dl * self.config.KP_extent * (2 ** layer)

                    # Get the distance to closest input point
                    KP_min_d2 = tf.reduce_min(deformed_d2, axis=1)

                    # Normalize KP locations to be independant from layers
                    KP_min_d2 = KP_min_d2 / (KP_extent ** 2)

                    # Loss will be the square distance to closest input point.
                    # Mean => loss independent from the number of input points
                    offset_losses += [tf.reduce_mean(KP_min_d2)]

                if op.name.endswith('deformed_KP'):

                    # Get deformed positions
                    deformed_KP = op.outputs[0]

                    # Layer index
                    layer = int(op.name.split('/')[1].split('_')[-1])

                    # Radius of deformed convolution for this layer
                    KP_extent = self.config.first_subsampling_dl * self.config.KP_extent * (2 ** layer)

                    # Normalized KP locations
                    KP_locs = deformed_KP / KP_extent

                    # Point should not be close to each other
                    for i in range(self.config.num_kernel_points):
                        other_KP = tf.stop_gradient(tf.concat([KP_locs[:, :i, :], KP_locs[:, i + 1:, :]], axis=1))
                        distances = tf.sqrt(1e-10 + tf.reduce_sum(tf.square(other_KP - KP_locs[:, i:i + 1, :]), axis=2))
                        repulsive_losses = tf.reduce_sum(tf.square(tf.maximum(0.0, 1.5 - distances)), axis=1)
                        offset_losses += [tf.reduce_mean(repulsive_losses)]

        elif self.config.offsets_loss != 'none':
            raise ValueError('Unknown offset loss')

        if len(offset_losses) > 0:
            self.offsets_loss = self.config.offsets_decay * tf.add_n(offset_losses)
        else:
            self.offsets_loss = tf.constant(0, dtype=tf.float32)

        return self.offsets_loss + self.gaussian_loss + self.regularization_loss

    def parameters_log(self):

        self.config.save(self.saving_path)